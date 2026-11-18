#!/usr/bin/env python3
import os
import glob
import json
import sys

def discover_catalogs():
    known_targets = [
        {
            'key': 'landscape_keepers',
            'name': 'Landscape Keepers (Terrestrial)',
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
            'key': 'pegasus_terrestrial',
            'name': 'Pegasus Terrestrial Keepers',
            'rel_folder': '7 Terestrial Catalog/KEEPERS/Terestrial Keepers ',
            'img_subdirs': ['Images/Landscape and Pano Keepers', 'Images']
        }
    ]

    found = []
    seen_catalogs = set()

    # Get all mounted volumes
    vols = [v for v in glob.glob('/Volumes/*') if os.path.isdir(v)]
    
    # Priority sort: 2TB_Archive first, then Pegasus, then others
    def vol_sort(v):
        v_lower = os.path.basename(v).lower()
        if '2tb' in v_lower or 'archive' in v_lower or 'ssd' in v_lower:
            return 0
        if 'pegasus' in v_lower:
            return 1
        return 2
    vols.sort(key=vol_sort)

    # 1. Check known targets across all mounted volumes
    for vol in vols:
        vol_name = os.path.basename(vol)
        for target in known_targets:
            candidate_dir = os.path.join(vol, target['rel_folder'])
            if os.path.exists(candidate_dir):
                lrcats = [
                    os.path.join(candidate_dir, f)
                    for f in os.listdir(candidate_dir)
                    if f.endswith('.lrcat') and not f.startswith('._')
                ]
                if lrcats:
                    lrcats.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                    cat_path = lrcats[0]
                    if cat_path in seen_catalogs:
                        continue
                    seen_catalogs.add(cat_path)

                    img_path = candidate_dir
                    for sub in target['img_subdirs']:
                        sub_full = os.path.join(candidate_dir, sub)
                        if os.path.exists(sub_full):
                            img_path = sub_full
                            break

                    found.append({
                        'key': target['key'],
                        'name': target['name'],
                        'volume': vol_name,
                        'catalog_path': cat_path,
                        'images_folder': img_path,
                        'display_label': f"{target['name']} [{vol_name}]"
                    })

    # 2. General scan on the 2TB drive for any other catalog folders
    for vol in vols:
        vol_lower = os.path.basename(vol).lower()
        if '2tb' in vol_lower or 'archive' in vol_lower or 'ssd' in vol_lower:
            try:
                subdirs = [
                    os.path.join(vol, d) for d in os.listdir(vol)
                    if os.path.isdir(os.path.join(vol, d))
                    and not d.startswith('.') and not d.startswith('$')
                ]
                for d in subdirs:
                    lrcats = [
                        os.path.join(d, f) for f in os.listdir(d)
                        if f.endswith('.lrcat') and not f.startswith('._')
                    ]
                    if lrcats:
                        lrcats.sort(key=lambda p: os.path.getmtime(p), reverse=True)
                        cat_path = lrcats[0]
                        if cat_path in seen_catalogs:
                            continue
                        seen_catalogs.add(cat_path)

                        # Find image directory
                        img_path = d
                        for cand in ['Images', 'Keepers Images', 'Keepers']:
                            p = os.path.join(d, cand)
                            if os.path.exists(p):
                                img_path = p
                                break

                        folder_name = os.path.basename(d)
                        found.append({
                            'key': f"custom_{folder_name.lower().replace(' ', '_')}",
                            'name': folder_name,
                            'volume': os.path.basename(vol),
                            'catalog_path': cat_path,
                            'images_folder': img_path,
                            'display_label': f"{folder_name} [{os.path.basename(vol)}]"
                        })
            except Exception:
                pass

    return found

if __name__ == '__main__':
    out_path = sys.argv[1] if len(sys.argv) > 1 else '/tmp/keepers_catalogs.json'
    catalogs = discover_catalogs()
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(catalogs, f, indent=2)
