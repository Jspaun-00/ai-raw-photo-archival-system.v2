#!/usr/bin/env python3
import os
import glob
import json
import sys

def is_system_or_hidden_volume(vol_path):
    vname = os.path.basename(vol_path).lower()
    if not vname or vname.startswith('.'):
        return True
    system_names = {'macintosh hd', 'macintosh hd - data', 'recovery', 'preboot', 'vm', 'update'}
    return vname in system_names

def is_excluded_folder(folder_name):
    lower = folder_name.lower()
    if not lower or lower.startswith('.') or lower.startswith('$'):
        return True
    excluded_names = {
        'operating files (do not touch)',
        'mr_darkroom_studio',
        'guides and plugins',
        'system volume information',
        'backups',
        'old lightroom catalogs',
        '$recycle.bin',
        '.trashes',
        '.spotlight-v100',
        '.fseventsd'
    }
    if lower in excluded_names:
        return True
    if lower.endswith('.app') or lower.endswith('.lrdata') or lower.endswith('.lrplugin'):
        return True
    return False

def get_best_lrcat_in_dir(dir_path):
    if not os.path.isdir(dir_path):
        return None
    try:
        entries = [
            os.path.join(dir_path, f) for f in os.listdir(dir_path)
            if f.endswith('.lrcat') and not f.startswith('._')
        ]
        if not entries:
            return None
        # Sort by modification time, newest first
        entries.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        return entries[0]
    except Exception:
        return None

def resolve_images_folder(cat_dir, preferred_subdirs=None):
    if preferred_subdirs:
        for sub in preferred_subdirs:
            sub_full = os.path.join(cat_dir, sub)
            if os.path.exists(sub_full):
                return sub_full
    for cand in ['Images', 'Keepers Images', 'Keepers', 'Exported Images', 'Photos']:
        p = os.path.join(cat_dir, cand)
        if os.path.exists(p):
            return p
    return os.path.join(cat_dir, 'Images')

def discover_catalogs():
    known_targets = [
        {
            'key': 'landscape_keepers',
            'name': 'Landscape Keepers',
            'rel_folder': 'Landscape Keepers',
            'img_subdirs': ['Images']
        },
        {
            'key': 'aerial_keepers',
            'name': 'Aerial Keepers',
            'rel_folder': 'Aerial Keepers',
            'img_subdirs': ['Keepers Images', 'Images']
        },
        {
            'key': 'family_catalog',
            'name': 'Family Catalog',
            'rel_folder': 'Family Catalog',
            'img_subdirs': ['Images']
        },
        {
            'key': 'aerial_catalog',
            'name': 'Aerial Catalog',
            'rel_folder': 'Aerial Catalog',
            'img_subdirs': ['Images', 'Keepers Images']
        },
        {
            'key': 'pegasus_terrestrial',
            'name': 'Pegasus Terrestrial Keepers',
            'rel_folder': '7 Terestrial Catalog/KEEPERS/Terestrial Keepers ',
            'img_subdirs': ['Images/Landscape and Pano Keepers', 'Images']
        }
    ]

    found = []
    seen_catalogs = set()

    # Get all mounted volumes
    vols = [v for v in glob.glob('/Volumes/*') if os.path.isdir(v) and not is_system_or_hidden_volume(v)]
    
    # Priority sort: 2TB_Archive / SSDs first, then others
    def vol_sort(v):
        v_lower = os.path.basename(v).lower()
        if '2tb' in v_lower or 'archive' in v_lower or 'ssd' in v_lower:
            return 0
        if 'pegasus' in v_lower:
            return 1
        return 2
    vols.sort(key=vol_sort)

    # Add local Pictures & Desktop
    home_dir = os.path.expanduser('~')
    extra_roots = []
    for loc in [os.path.join(home_dir, 'Pictures'), os.path.join(home_dir, 'Desktop')]:
        if os.path.isdir(loc):
            extra_roots.append(loc)

    # 1. Match known catalog target definitions across all mounted external volumes
    for vol in vols:
        vol_name = os.path.basename(vol)
        for target in known_targets:
            candidate_dir = os.path.join(vol, target['rel_folder'])
            if os.path.exists(candidate_dir):
                cat_path = get_best_lrcat_in_dir(candidate_dir)
                if cat_path and cat_path not in seen_catalogs:
                    seen_catalogs.add(cat_path)
                    img_path = resolve_images_folder(candidate_dir, target['img_subdirs'])
                    found.append({
                        'key': f"{target['key']}_{vol_name.lower()}",
                        'name': target['name'],
                        'volume': vol_name,
                        'catalog_path': cat_path,
                        'images_folder': img_path,
                        'display_label': f"{target['name']} [{vol_name}]"
                    })

    # 2. Comprehensive multi-level scan of ALL mounted external volumes + local Pictures/Desktop
    scan_roots = [(v, os.path.basename(v)) for v in vols] + [(r, os.path.basename(r)) for r in extra_roots]

    for root_path, root_label in scan_roots:
        try:
            # A) Check root level of volume (e.g. /Volumes/TravelDrive/*.lrcat)
            root_cat = get_best_lrcat_in_dir(root_path)
            if root_cat and root_cat not in seen_catalogs:
                seen_catalogs.add(root_cat)
                cat_name = os.path.basename(os.path.dirname(root_cat)) or root_label
                found.append({
                    'key': f"root_{root_label.lower()}",
                    'name': cat_name,
                    'volume': root_label,
                    'catalog_path': root_cat,
                    'images_folder': resolve_images_folder(root_path),
                    'display_label': f"{cat_name} [{root_label}]"
                })

            # B) Check 1st & 2nd level subdirectories
            subdirs = [
                os.path.join(root_path, d) for d in os.listdir(root_path)
                if os.path.isdir(os.path.join(root_path, d)) and not is_excluded_folder(d)
            ]
            
            for d in subdirs:
                # 1st level check
                lrcat_1 = get_best_lrcat_in_dir(d)
                if lrcat_1 and lrcat_1 not in seen_catalogs:
                    seen_catalogs.add(lrcat_1)
                    folder_name = os.path.basename(d)
                    found.append({
                        'key': f"dyn_{folder_name.lower().replace(' ', '_')}_{root_label.lower()}",
                        'name': folder_name,
                        'volume': root_label,
                        'catalog_path': lrcat_1,
                        'images_folder': resolve_images_folder(d),
                        'display_label': f"{folder_name} [{root_label}]"
                    })
                
                # 2nd level check inside subdirectory
                try:
                    sub_subdirs = [
                        os.path.join(d, sd) for sd in os.listdir(d)
                        if os.path.isdir(os.path.join(d, sd)) and not is_excluded_folder(sd)
                    ]
                    for sd in sub_subdirs:
                        lrcat_2 = get_best_lrcat_in_dir(sd)
                        if lrcat_2 and lrcat_2 not in seen_catalogs:
                            seen_catalogs.add(lrcat_2)
                            sub_folder_name = os.path.basename(sd)
                            parent_folder_name = os.path.basename(d)
                            display_name = f"{parent_folder_name} / {sub_folder_name}"
                            found.append({
                                'key': f"dyn2_{sub_folder_name.lower().replace(' ', '_')}_{root_label.lower()}",
                                'name': sub_folder_name,
                                'volume': root_label,
                                'catalog_path': lrcat_2,
                                'images_folder': resolve_images_folder(sd),
                                'display_label': f"{display_name} [{root_label}]"
                            })
                except Exception:
                    pass

        except Exception:
            pass

    return found

if __name__ == '__main__':
    out_path = sys.argv[1] if len(sys.argv) > 1 else '/tmp/keepers_catalogs.json'
    catalogs = discover_catalogs()
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(catalogs, f, indent=2)
    print(f"Discovered {len(catalogs)} catalog(s). Written to {out_path}")
