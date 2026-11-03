"""
Domain Gazetteers, Multi-Tier Ontologies, Portfolio Categories, and Tag Safelists
for MR Darkroom (extracted from stage2_vlm.py for clean modular architecture).
"""

from typing import Any, Dict, List, Optional, Set, Tuple

GENERIC_NOISE_TAGS: Set[str] = {
    "unsharp",
    "monochrome",
    "needs_review",
    "location_review_needed",
    "location_burst_inherited",
    "stitched_panorama",
    "exposure_bracket_hdr_sequence",
    "raw",
    "iiq",
    "tif",
    "dng",
    "jpg",
    "mitch rouse aerials",
    "mitch_rouse_aerials",
    "mitch rouse",
    "aerials",
    "msr",
    "keepers",
    "to print",
    "book",
    "selects",
    "archive",
    "unknown",
    "none",
    "general",
    "landscape",
    "aerial",
    "terrestrial",
    "west coast imaging*  alice",
    "west coast imaging* alice",
    "west coast imaging",
    "alice",
    "mitch shooting",
    "mitch_shooting",
    "tripeast",
    "395",
    "eye-level",
    "eye-level terrestrial",
    "national parks & mountains",
    "sharp",
    "bro just look",
    "what's",
    "whats",
    "look at it",
    "tag what's in there",
    "floor",
    "wall",
    "light switch",
    "cup of water",
    "generate",
    "bars",
}

AERIAL_ONLY_LANDMARKS: Dict[str, Tuple[str, str]] = {
    "taft": ("Taft Oil Field", "California"),
    "taft oil field": ("Taft Oil Field", "California"),
    "palouse": ("Palouse", "Washington"),
    "the palouse": ("Palouse", "Washington"),
}

# Multi-Tier Ontology Dictionaries (Specific -> (Canonical Specific, Mid-Tier List, Parent-Tier List, Hierarchical Path))
_ANIMAL_ONTOLOGY: Dict[str, Tuple[str, List[str], List[str], str]] = {
    "bison": ("Bison", ["Buffalo", "Mammals", "Ungulates"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Wildlife|Bison"),
    "buffalo": ("Buffalo", ["Bison", "Mammals", "Ungulates"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Wildlife|Bison"),
    "american bison": ("Bison", ["Buffalo", "Mammals"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Wildlife|Bison"),
    "horse": ("Horse", ["Horses", "Equine", "Mammals"], ["Animal", "Animals", "Fauna"], "Subjects|Animals|Horses|Horse"),
    "horses": ("Horses", ["Horse", "Equine", "Mammals"], ["Animal", "Animals", "Fauna"], "Subjects|Animals|Horses"),
    "quarter horse": ("Quarter Horse", ["Horse", "Horses", "Equine"], ["Animal", "Animals", "Fauna"], "Subjects|Animals|Horses|Quarter_Horse"),
    "quarter horses": ("Quarter Horses", ["Horse", "Horses", "Equine"], ["Animal", "Animals", "Fauna"], "Subjects|Animals|Horses|Quarter_Horse"),
    "stallion": ("Stallion", ["Horse", "Horses", "Equine"], ["Animal", "Animals", "Fauna"], "Subjects|Animals|Horses"),
    "mare": ("Mare", ["Horse", "Horses", "Equine"], ["Animal", "Animals", "Fauna"], "Subjects|Animals|Horses"),
    "foal": ("Foal", ["Horse", "Horses", "Equine"], ["Animal", "Animals", "Fauna"], "Subjects|Animals|Horses"),
    "mustang": ("Mustang", ["Horse", "Horses", "Equine"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Horses|Mustang"),
    "equine": ("Equine", ["Horse", "Horses"], ["Animal", "Animals", "Fauna"], "Subjects|Animals|Horses"),
    "cattle": ("Cattle", ["Cow", "Cows", "Livestock", "Mammals"], ["Animal", "Animals", "Fauna"], "Subjects|Animals|Livestock|Cattle"),
    "cow": ("Cow", ["Cattle", "Cows", "Livestock", "Mammals"], ["Animal", "Animals", "Fauna"], "Subjects|Animals|Livestock|Cattle"),
    "cows": ("Cows", ["Cow", "Cattle", "Livestock", "Mammals"], ["Animal", "Animals", "Fauna"], "Subjects|Animals|Livestock|Cattle"),
    "black angus": ("Black Angus", ["Cattle", "Cow", "Livestock"], ["Animal", "Animals", "Fauna"], "Subjects|Animals|Livestock|Black_Angus"),
    "bull": ("Bull", ["Cattle", "Cow", "Livestock"], ["Animal", "Animals", "Fauna"], "Subjects|Animals|Livestock|Cattle"),
    "steer": ("Steer", ["Cattle", "Livestock"], ["Animal", "Animals", "Fauna"], "Subjects|Animals|Livestock|Cattle"),
    "calf": ("Calf", ["Cattle", "Cow", "Livestock"], ["Animal", "Animals", "Fauna"], "Subjects|Animals|Livestock|Cattle"),
    "longhorn": ("Longhorn", ["Cattle", "Livestock"], ["Animal", "Animals", "Fauna"], "Subjects|Animals|Livestock|Longhorn"),
    "livestock": ("Livestock", ["Cattle", "Ranch_Animals"], ["Animal", "Animals", "Fauna"], "Subjects|Animals|Livestock"),
    "elk": ("Elk", ["Mammals", "Ungulates"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Wildlife|Elk"),
    "deer": ("Deer", ["Mammals", "Ungulates"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Wildlife|Deer"),
    "mule deer": ("Mule Deer", ["Deer", "Mammals"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Wildlife|Deer"),
    "moose": ("Moose", ["Mammals", "Ungulates"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Wildlife|Moose"),
    "pronghorn": ("Pronghorn", ["Antelope", "Mammals"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Wildlife|Pronghorn"),
    "antelope": ("Antelope", ["Pronghorn", "Mammals"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Wildlife|Antelope"),
    "bighorn": ("Bighorn Sheep", ["Sheep", "Mammals"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Wildlife|Bighorn_Sheep"),
    "sheep": ("Sheep", ["Livestock", "Mammals"], ["Animal", "Animals", "Fauna"], "Subjects|Animals|Livestock|Sheep"),
    "bear": ("Bear", ["Mammals"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Wildlife|Bear"),
    "grizzly": ("Grizzly Bear", ["Bear", "Mammals"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Wildlife|Grizzly_Bear"),
    "coyote": ("Coyote", ["Canine", "Mammals"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Wildlife|Coyote"),
    "wolf": ("Wolf", ["Canine", "Mammals"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Wildlife|Wolf"),
    "fox": ("Fox", ["Canine", "Mammals"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Wildlife|Fox"),
    "dog": ("Dog", ["Canine", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Dog"),
    "dogs": ("Dogs", ["Dog", "Canine", "Pet", "Mammals"], ["Animals", "Pets", "Fauna"], "Subjects|Animals|Pets|Dog"),
    "puppy": ("Puppy", ["Dog", "Canine", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Dog"),
    "chihuahua": ("Chihuahua", ["Dog", "Canine", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Dog|Chihuahua"),
    "rat terrier": ("Rat Terrier", ["Dog", "Canine", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Dog|Rat_Terrier"),
    "jack russell terrier": ("Jack Russell Terrier", ["Dog", "Canine", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Dog|Jack_Russell_Terrier"),
    "french bulldog": ("French Bulldog", ["Dog", "Canine", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Dog|French_Bulldog"),
    "english bulldog": ("English Bulldog", ["Dog", "Canine", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Dog|English_Bulldog"),
    "corgi": ("Corgi", ["Dog", "Canine", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Dog|Corgi"),
    "dachshund": ("Dachshund", ["Dog", "Canine", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Dog|Dachshund"),
    "beagle": ("Beagle", ["Dog", "Canine", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Dog|Beagle"),
    "golden retriever": ("Golden Retriever", ["Dog", "Canine", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Dog|Golden_Retriever"),
    "labrador retriever": ("Labrador Retriever", ["Dog", "Canine", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Dog|Labrador_Retriever"),
    "german shepherd": ("German Shepherd", ["Dog", "Canine", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Dog|German_Shepherd"),
    "australian shepherd": ("Australian Shepherd", ["Dog", "Canine", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Dog|Australian_Shepherd"),
    "border collie": ("Border Collie", ["Dog", "Canine", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Dog|Border_Collie"),
    "poodle / doodle": ("Poodle / Doodle", ["Dog", "Canine", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Dog|Poodle_Doodle"),
    "siberian husky": ("Siberian Husky", ["Dog", "Canine", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Dog|Siberian_Husky"),
    "boxer": ("Boxer", ["Dog", "Canine", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Dog|Boxer"),
    "pit bull terrier": ("Pit Bull Terrier", ["Dog", "Canine", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Dog|Pit_Bull_Terrier"),
    "pomeranian": ("Pomeranian", ["Dog", "Canine", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Dog|Pomeranian"),
    "spaniel": ("Spaniel", ["Dog", "Canine", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Dog|Spaniel"),
    "feline": ("Feline", ["Cat"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Cat"),
    "bee": ("Bee", ["Honeybee", "Insect", "Macro Photography"], ["Wildlife", "Fauna", "Animals"], "Subjects|Wildlife_And_Insects|Bee"),
    "bees": ("Bees", ["Bee", "Insect", "Macro Photography"], ["Wildlife", "Fauna", "Animals"], "Subjects|Wildlife_And_Insects|Bee"),
    "honeybee": ("Honeybee", ["Bee", "Insect", "Macro Photography"], ["Wildlife", "Fauna", "Animals"], "Subjects|Wildlife_And_Insects|Bee"),
    "honeybees": ("Honeybees", ["Bee", "Insect", "Macro Photography"], ["Wildlife", "Fauna", "Animals"], "Subjects|Wildlife_And_Insects|Bee"),
    "bumblebee": ("Bumblebee", ["Bee", "Insect", "Macro Photography"], ["Wildlife", "Fauna", "Animals"], "Subjects|Wildlife_And_Insects|Bee"),
    "wasp": ("Wasp", ["Insect", "Macro Photography"], ["Wildlife", "Fauna", "Animals"], "Subjects|Wildlife_And_Insects|Wasp"),
    "insect": ("Insect", ["Bug", "Macro Photography"], ["Wildlife", "Fauna", "Animals"], "Subjects|Wildlife_And_Insects|Insect"),
    "insects": ("Insects", ["Insect", "Macro Photography"], ["Wildlife", "Fauna", "Animals"], "Subjects|Wildlife_And_Insects|Insect"),
    "cat": ("Cat", ["Feline", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Cat"),
    "cats": ("Cats", ["Cat", "Feline", "Pet", "Mammals"], ["Animals", "Pets", "Fauna"], "Subjects|Animals|Pets|Cat"),
    "kitten": ("Kitten", ["Cat", "Feline", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Cat"),
    "scottish fold": ("Scottish Fold", ["Cat", "Feline", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Cat|Scottish_Fold"),
    "british shorthair": ("British Shorthair", ["Cat", "Feline", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Cat|British_Shorthair"),
    "american shorthair": ("American Shorthair", ["Cat", "Feline", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Cat|American_Shorthair"),
    "tabby cat": ("Tabby Cat", ["Cat", "Feline", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Cat|Tabby_Cat"),
    "orange tabby": ("Orange Tabby", ["Tabby Cat", "Cat", "Feline", "Pet"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Cat|Orange_Tabby"),
    "black cat": ("Black Cat", ["Cat", "Feline", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Cat|Black_Cat"),
    "tuxedo cat": ("Tuxedo Cat", ["Cat", "Feline", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Cat|Tuxedo_Cat"),
    "calico": ("Calico", ["Cat", "Feline", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Cat|Calico"),
    "tortoiseshell": ("Tortoiseshell", ["Cat", "Feline", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Cat|Tortoiseshell"),
    "siamese": ("Siamese", ["Cat", "Feline", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Cat|Siamese"),
    "ragdoll": ("Ragdoll", ["Cat", "Feline", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Cat|Ragdoll"),
    "maine coon / longhair": ("Maine Coon / Longhair", ["Cat", "Feline", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Cat|Maine_Coon"),
    "bengal": ("Bengal", ["Cat", "Feline", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Cat|Bengal"),
    "persian": ("Persian", ["Cat", "Feline", "Pet", "Mammals"], ["Animal", "Pets", "Fauna"], "Subjects|Animals|Pets|Cat|Persian"),
    "arabian horse": ("Arabian Horse", ["Horse", "Horses", "Equine"], ["Animal", "Animals", "Fauna"], "Subjects|Animals|Horses|Arabian_Horse"),
    "thoroughbred": ("Thoroughbred", ["Horse", "Horses", "Equine"], ["Animal", "Animals", "Fauna"], "Subjects|Animals|Horses|Thoroughbred"),
    "clydesdale / draft horse": ("Clydesdale / Draft Horse", ["Horse", "Horses", "Equine"], ["Animal", "Animals", "Fauna"], "Subjects|Animals|Horses|Draft_Horse"),
    "appaloosa": ("Appaloosa", ["Horse", "Horses", "Equine"], ["Animal", "Animals", "Fauna"], "Subjects|Animals|Horses|Appaloosa"),
    "paint / pinto horse": ("Paint / Pinto Horse", ["Horse", "Horses", "Equine"], ["Animal", "Animals", "Fauna"], "Subjects|Animals|Horses|Paint_Horse"),
    "palomino": ("Palomino", ["Horse", "Horses", "Equine"], ["Animal", "Animals", "Fauna"], "Subjects|Animals|Horses|Palomino"),
    "pony": ("Pony", ["Horse", "Horses", "Equine"], ["Animal", "Animals", "Fauna"], "Subjects|Animals|Horses|Pony"),
    "great blue heron": ("Great Blue Heron", ["Heron", "Bird", "Birds", "Wading_Bird"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Great_Blue_Heron"),
    "snowy egret": ("Snowy Egret", ["Egret", "Bird", "Birds", "Wading_Bird"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Snowy_Egret"),
    "brown pelican": ("Brown Pelican", ["Pelican", "Bird", "Birds", "Seabird"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Brown_Pelican"),
    "avocet": ("Avocet", ["Bird", "Birds", "Wading_Bird"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Avocet"),
    "cormorant": ("Cormorant", ["Bird", "Birds", "Seabird"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Cormorant"),
    "red-tailed hawk": ("Red-Tailed Hawk", ["Hawk", "Bird", "Birds", "Raptor"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Red_Tailed_Hawk"),
    "great horned owl": ("Great Horned Owl", ["Owl", "Bird", "Birds", "Raptor"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Great_Horned_Owl"),
    "hummingbird": ("Hummingbird", ["Bird", "Birds"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Hummingbird"),
    "mallard": ("Mallard", ["Duck", "Bird", "Birds", "Waterfowl"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Mallard"),
    "canada goose": ("Canada Goose", ["Goose", "Geese", "Bird", "Birds", "Waterfowl"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Canada_Goose"),
    "grizzly / black bear": ("Grizzly / Black Bear", ["Bear", "Mammals"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Wildlife|Bear"),
    "red fox": ("Red Fox", ["Fox", "Canine", "Mammals"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Wildlife|Red_Fox"),
    "sea otter": ("Sea Otter", ["Marine_Life", "Mammals"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Marine|Sea_Otter"),
    "seal / sea lion": ("Seal / Sea Lion", ["Seal", "Sea Lion", "Marine_Life", "Mammals"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Marine|Seal_Sea_Lion"),
    "humpback whale": ("Humpback Whale", ["Whale", "Marine_Life", "Mammals"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Marine|Humpback_Whale"),
    "pet": ("Pet", ["Pets", "Domestic_Animal"], ["Animal", "Animals"], "Subjects|Animals|Pets"),
    "pets": ("Pets", ["Pet", "Domestic_Animal"], ["Animal", "Animals"], "Subjects|Animals|Pets"),
    "frog": ("Frog", ["Amphibian"], ["Animal", "Wildlife", "Fauna"], "Subjects|Animals|Wildlife|Frog"),
    "frogs": ("Frogs", ["Amphibian"], ["Animals", "Wildlife", "Fauna"], "Subjects|Animals|Wildlife|Frog"),
    "bird": ("Bird", ["Avian"], ["Animal", "Wildlife", "Fauna"], "Subjects|Animals|Birds"),
    "birds": ("Birds", ["Avian"], ["Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds"),
    "pelican": ("Pelican", ["Bird", "Birds", "Seabird", "Waterfowl"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Pelican"),
    "pelicans": ("Pelicans", ["Pelican", "Bird", "Birds", "Seabird"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Pelican"),
    "eagle": ("Eagle", ["Bird", "Birds", "Raptor"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Eagle"),
    "bald eagle": ("Bald Eagle", ["Eagle", "Bird", "Birds", "Raptor"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Bald_Eagle"),
    "hawk": ("Hawk", ["Bird", "Birds", "Raptor"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Hawk"),
    "osprey": ("Osprey", ["Bird", "Birds", "Raptor"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Osprey"),
    "owl": ("Owl", ["Bird", "Birds", "Raptor"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Owl"),
    "heron": ("Heron", ["Bird", "Birds", "Wading_Bird"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Heron"),
    "egret": ("Egret", ["Bird", "Birds", "Wading_Bird"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Egret"),
    "crane": ("Crane", ["Bird", "Birds", "Wading_Bird"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Crane"),
    "sandhill crane": ("Sandhill Crane", ["Crane", "Bird", "Birds"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Sandhill_Crane"),
    "goose": ("Goose", ["Geese", "Bird", "Birds", "Waterfowl"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Waterfowl"),
    "geese": ("Geese", ["Goose", "Bird", "Birds", "Waterfowl"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Waterfowl"),
    "snow geese": ("Snow Geese", ["Geese", "Bird", "Birds", "Waterfowl"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Snow_Geese"),
    "duck": ("Duck", ["Ducks", "Bird", "Birds", "Waterfowl"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Waterfowl"),
    "ducks": ("Ducks", ["Duck", "Bird", "Birds", "Waterfowl"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Waterfowl"),
    "waterfowl": ("Waterfowl", ["Bird", "Birds"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Waterfowl"),
    "gull": ("Gull", ["Seagull", "Bird", "Birds", "Seabird"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Gull"),
    "seagull": ("Seagull", ["Gull", "Bird", "Birds", "Seabird"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Birds|Gull"),
    "alligator": ("Alligator", ["Reptile"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Wildlife|Alligator"),
    "whale": ("Whale", ["Marine_Life", "Mammals"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Marine|Whale"),
    "dolphin": ("Dolphin", ["Marine_Life", "Mammals"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Marine|Dolphin"),
    "seal": ("Seal", ["Marine_Life", "Mammals"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Marine|Seal"),
    "sea lion": ("Sea Lion", ["Marine_Life", "Mammals"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Marine|Sea_Lion"),
    "wildlife": ("Wildlife", ["Fauna"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals|Wildlife"),
    "animal": ("Animal", ["Fauna"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals"),
    "animals": ("Animals", ["Fauna"], ["Animal", "Animals", "Wildlife", "Fauna"], "Subjects|Animals"),
}

_PEOPLE_ONTOLOGY: Dict[str, Tuple[str, List[str], List[str], str]] = {
    "mitch shooting": ("Mitch Rouse (Subject)", ["Photographer", "Man", "Male", "Portrait"], ["Person", "People", "Human"], "Identity|Mitch Rouse"),
    "self portrait": ("Mitch Rouse (Subject)", ["Photographer", "Man", "Male", "Portrait"], ["Person", "People", "Human"], "Identity|Mitch Rouse"),
    "photographer": ("Photographer", ["Portrait"], ["Person", "People", "Human"], "Subjects|People|Photographer"),
    "man": ("Man", ["Male", "Adult"], ["Person", "People", "Human"], "Subjects|People|Man"),
    "men": ("Men", ["Man", "Male", "Adult"], ["Person", "People", "Human"], "Subjects|People|Man"),
    "male": ("Male", ["Man"], ["Person", "People", "Human"], "Subjects|People|Man"),
    "woman": ("Woman", ["Female", "Adult"], ["Person", "People", "Human"], "Subjects|People|Woman"),
    "women": ("Women", ["Woman", "Female", "Adult"], ["Person", "People", "Human"], "Subjects|People|Woman"),
    "female": ("Female", ["Woman"], ["Person", "People", "Human"], "Subjects|People|Woman"),
    "boy": ("Boy", ["Male", "Child", "Youth"], ["Person", "People", "Human"], "Subjects|People|Boy"),
    "girl": ("Girl", ["Female", "Child", "Youth"], ["Person", "People", "Human"], "Subjects|People|Girl"),
    "child": ("Child", ["Youth"], ["Person", "People", "Human"], "Subjects|People|Child"),
    "children": ("Children", ["Child", "Youth"], ["Person", "People", "Human"], "Subjects|People|Child"),
    "family": ("Family", ["Portrait", "Group"], ["Person", "People", "Human"], "Subjects|People|Family"),
    "portrait": ("Portrait", ["Subject"], ["Person", "People", "Human"], "Subjects|People|Portrait"),
    "cowboy": ("Cowboy", ["Rancher", "Rider", "Man", "Male"], ["Person", "People", "Human"], "Subjects|People|Cowboy"),
    "cowboys": ("Cowboys", ["Cowboy", "Rancher", "Rider", "Man"], ["Person", "People", "Human"], "Subjects|People|Cowboy"),
    "rancher": ("Rancher", ["Cowboy", "Worker"], ["Person", "People", "Human"], "Subjects|People|Rancher"),
    "wrangler": ("Wrangler", ["Cowboy", "Rancher", "Rider"], ["Person", "People", "Human"], "Subjects|People|Rancher"),
    "rider": ("Rider", ["Equestrian"], ["Person", "People", "Human"], "Subjects|People|Rider"),
    "horseback rider": ("Horseback Rider", ["Rider", "Cowboy", "Horse"], ["Person", "People", "Human", "Animal", "Animals"], "Subjects|People|Rider"),
    "worker": ("Worker", ["Laborer"], ["Person", "People", "Human"], "Subjects|People|Worker"),
    "farmer": ("Farmer", ["Worker", "Agriculture"], ["Person", "People", "Human"], "Subjects|People|Farmer"),
    "pilot": ("Pilot", ["Aviation"], ["Person", "People", "Human"], "Subjects|People|Pilot"),
    "hiker": ("Hiker", ["Outdoor_Recreation"], ["Person", "People", "Human"], "Subjects|People|Hiker"),
    "surfer": ("Surfer", ["Ocean_Sports"], ["Person", "People", "Human"], "Subjects|People|Surfer"),
    "person": ("Person", ["Individual"], ["Person", "People", "Human"], "Subjects|People"),
    "people": ("People", ["Person"], ["Person", "People", "Human"], "Subjects|People"),
    "human": ("Human", ["Person"], ["Person", "People", "Human"], "Subjects|People"),
    "mirror selfie": ("Mirror Selfie", ["Selfie", "Portrait", "Mirror"], ["Person", "People", "Human"], "Subjects|People|Mirror_Selfie"),
    "selfie": ("Selfie", ["Mirror Selfie", "Portrait"], ["Person", "People", "Human"], "Subjects|People|Selfie"),
}

_FLORA_ONTOLOGY: Dict[str, Tuple[str, List[str], List[str], str]] = {
    "lupine": ("Lupine", ["Wildflowers", "Flower", "Flowers"], ["Plants", "Flora", "Botanical"], "Subjects|Flora|Wildflowers|Lupine"),
    "poppy": ("Poppy", ["Poppies", "Wildflowers", "Flower", "Flowers"], ["Plants", "Flora", "Botanical"], "Subjects|Flora|Wildflowers|Poppy"),
    "poppies": ("Poppies", ["Poppy", "Wildflowers", "Flower", "Flowers"], ["Plants", "Flora", "Botanical"], "Subjects|Flora|Wildflowers|Poppy"),
    "wildflower": ("Wildflower", ["Wildflowers", "Flower", "Flowers"], ["Plants", "Flora", "Botanical"], "Subjects|Flora|Wildflowers"),
    "wildflowers": ("Wildflowers", ["Wildflower", "Flower", "Flowers"], ["Plants", "Flora", "Botanical"], "Subjects|Flora|Wildflowers"),
    "flower": ("Flower", ["Flowers", "Wildflowers"], ["Plants", "Flora", "Botanical"], "Subjects|Flora|Flowers"),
    "flowers": ("Flowers", ["Flower", "Wildflowers"], ["Plants", "Flora", "Botanical"], "Subjects|Flora|Flowers"),
    "sunflower": ("Sunflower", ["Wildflowers", "Flower", "Flowers"], ["Plants", "Flora", "Botanical"], "Subjects|Flora|Wildflowers|Sunflower"),
    "yucca": ("Yucca", ["Desert_Flora", "Succulent"], ["Plants", "Flora", "Botanical"], "Subjects|Flora|Desert_Plants|Yucca"),
    "joshua tree": ("Joshua Tree", ["Yucca", "Tree", "Trees", "Desert_Flora"], ["Plants", "Flora", "Botanical"], "Subjects|Flora|Trees|Joshua_Tree"),
    "saguaro": ("Saguaro", ["Cactus", "Cacti", "Desert_Flora"], ["Plants", "Flora", "Botanical"], "Subjects|Flora|Desert_Plants|Saguaro"),
    "cactus": ("Cactus", ["Cacti", "Desert_Flora"], ["Plants", "Flora", "Botanical"], "Subjects|Flora|Desert_Plants|Cactus"),
    "cacti": ("Cacti", ["Cactus", "Desert_Flora"], ["Plants", "Flora", "Botanical"], "Subjects|Flora|Desert_Plants|Cactus"),
    "oak": ("Oak Tree", ["Tree", "Trees", "Forest"], ["Plants", "Flora"], "Subjects|Flora|Trees|Oak"),
    "oak tree": ("Oak Tree", ["Tree", "Trees", "Forest"], ["Plants", "Flora"], "Subjects|Flora|Trees|Oak"),
    "aspen": ("Aspen", ["Tree", "Trees", "Forest", "Autumn_Foliage"], ["Plants", "Flora"], "Subjects|Flora|Trees|Aspen"),
    "cypress": ("Cypress", ["Tree", "Trees", "Swamp", "Bayou"], ["Plants", "Flora"], "Subjects|Flora|Trees|Cypress"),
    "pine": ("Pine Tree", ["Tree", "Trees", "Conifer", "Forest"], ["Plants", "Flora"], "Subjects|Flora|Trees|Pine"),
    "redwood": ("Redwood", ["Tree", "Trees", "Forest"], ["Plants", "Flora"], "Subjects|Flora|Trees|Redwood"),
    "cottonwood": ("Cottonwood", ["Tree", "Trees"], ["Plants", "Flora"], "Subjects|Flora|Trees|Cottonwood"),
    "palm": ("Palm Tree", ["Tree", "Trees"], ["Plants", "Flora"], "Subjects|Flora|Trees|Palm"),
    "palm tree": ("Palm Tree", ["Tree", "Trees"], ["Plants", "Flora"], "Subjects|Flora|Trees|Palm"),
    "tree": ("Tree", ["Trees"], ["Plants", "Flora"], "Subjects|Flora|Trees"),
    "trees": ("Trees", ["Tree"], ["Plants", "Flora"], "Subjects|Flora|Trees"),
    "forest": ("Forest", ["Trees", "Woods"], ["Plants", "Flora"], "Subjects|Flora|Forest"),
    "kelp": ("Kelp", ["Giant_Kelp", "Marine_Flora", "Seaweed"], ["Plants", "Flora"], "Subjects|Flora|Marine|Kelp"),
    "giant kelp": ("Giant Kelp", ["Kelp", "Marine_Flora", "Seaweed"], ["Plants", "Flora"], "Subjects|Flora|Marine|Kelp"),
    "coast redwood": ("Coast Redwood", ["Redwood", "Tree", "Trees", "Forest"], ["Plants", "Flora"], "Subjects|Flora|Trees|Coast_Redwood"),
    "giant sequoia": ("Giant Sequoia", ["Redwood", "Tree", "Trees", "Forest"], ["Plants", "Flora"], "Subjects|Flora|Trees|Giant_Sequoia"),
    "quaking aspen": ("Quaking Aspen", ["Aspen", "Tree", "Trees", "Forest"], ["Plants", "Flora"], "Subjects|Flora|Trees|Quaking_Aspen"),
    "monterey cypress": ("Monterey Cypress", ["Cypress", "Tree", "Trees"], ["Plants", "Flora"], "Subjects|Flora|Trees|Monterey_Cypress"),
    "ponderosa pine": ("Ponderosa Pine", ["Pine Tree", "Tree", "Trees", "Conifer"], ["Plants", "Flora"], "Subjects|Flora|Trees|Ponderosa_Pine"),
    "orchard blossoms": ("Orchard Blossoms", ["Blossoms", "Flowers", "Tree", "Trees"], ["Plants", "Flora"], "Subjects|Flora|Trees|Orchard_Blossoms"),
    "saguaro cactus": ("Saguaro Cactus", ["Saguaro", "Cactus", "Desert_Flora"], ["Plants", "Flora"], "Subjects|Flora|Desert_Plants|Saguaro_Cactus"),
    "california poppies": ("California Poppies", ["Poppies", "Wildflowers", "Flowers"], ["Plants", "Flora"], "Subjects|Flora|Wildflowers|California_Poppies"),
    "monstera": ("Monstera", ["Houseplant", "Indoor_Plant"], ["Plants", "Flora"], "Subjects|Flora|Houseplants|Monstera"),
    "pothos": ("Pothos", ["Houseplant", "Indoor_Plant"], ["Plants", "Flora"], "Subjects|Flora|Houseplants|Pothos"),
    "fiddle leaf fig": ("Fiddle Leaf Fig", ["Houseplant", "Indoor_Plant", "Tree"], ["Plants", "Flora"], "Subjects|Flora|Houseplants|Fiddle_Leaf_Fig"),
    "succulent": ("Succulent", ["Houseplant", "Desert_Flora"], ["Plants", "Flora"], "Subjects|Flora|Houseplants|Succulent"),
    "morel / mushroom": ("Morel / Mushroom", ["Mushroom", "Fungi"], ["Plants", "Flora", "Botanical"], "Subjects|Flora|Fungi|Morel_Mushroom"),
    "mushroom": ("Morel / Mushroom", ["Mushroom", "Fungi"], ["Plants", "Flora", "Botanical"], "Subjects|Flora|Fungi|Morel_Mushroom"),
}

_STRUCTURE_ONTOLOGY: Dict[str, Tuple[str, List[str], List[str], str]] = {
    "barn": ("Barn", ["Farmstead", "Ranch", "Building"], ["Structure", "Structures", "Architecture", "Rural"], "Architecture|Ranch|Barn"),
    "old barn": ("Old Barn", ["Barn", "Farmstead", "Ranch", "Building"], ["Structure", "Structures", "Architecture", "Rural"], "Architecture|Ranch|Barn"),
    "red barn": ("Red Barn", ["Barn", "Farmstead", "Ranch", "Building"], ["Structure", "Structures", "Architecture", "Rural"], "Architecture|Ranch|Barn"),
    "farmhouse": ("Farmhouse", ["Farmstead", "Ranch", "House", "Building"], ["Structure", "Structures", "Architecture", "Rural"], "Architecture|Ranch|Farmhouse"),
    "farm house": ("Farmhouse", ["Farmstead", "Ranch", "House", "Building"], ["Structure", "Structures", "Architecture", "Rural"], "Architecture|Ranch|Farmhouse"),
    "farmstead": ("Farmstead", ["Barn", "Ranch", "Building"], ["Structure", "Structures", "Architecture", "Rural"], "Architecture|Ranch|Farmstead"),
    "homestead": ("Homestead", ["Cabin", "Ranch", "Building"], ["Structure", "Structures", "Architecture", "Rural"], "Architecture|Ranch|Homestead"),
    "cabin": ("Cabin", ["Log_Cabin", "Building"], ["Structure", "Structures", "Architecture", "Rural"], "Architecture|Ranch|Cabin"),
    "corral": ("Corral", ["Fence", "Ranch"], ["Structure", "Structures", "Rural"], "Architecture|Ranch|Corral"),
    "wooden fence": ("Wooden Fence", ["Fence", "Ranch"], ["Structure", "Structures", "Rural"], "Architecture|Ranch|Fence"),
    "fence": ("Fence", ["Ranch"], ["Structure", "Structures"], "Architecture|Ranch|Fence"),
    "windmill": ("Windmill", ["Ranch"], ["Structure", "Structures", "Architecture"], "Architecture|Ranch|Windmill"),
    "silo": ("Silo", ["Barn", "Farmstead", "Agriculture"], ["Structure", "Structures", "Architecture"], "Architecture|Ranch|Silo"),
    "pier": ("Pier", ["Coastal_Infrastructure", "Boardwalk"], ["Structure", "Structures", "Architecture", "Coast"], "Architecture|Coastal|Pier"),
    "wooden pier": ("Wooden Pier", ["Pier", "Coastal_Infrastructure"], ["Structure", "Structures", "Architecture", "Coast"], "Architecture|Coastal|Pier"),
    "jetty": ("Jetty", ["Breakwater", "Coastal_Infrastructure"], ["Structure", "Structures", "Coast"], "Architecture|Coastal|Jetty"),
    "lighthouse": ("Lighthouse", ["Beacon", "Coastal_Infrastructure", "Building"], ["Structure", "Structures", "Architecture", "Coast"], "Architecture|Coastal|Lighthouse"),
    "boat": ("Boat", ["Watercraft", "Vessel"], ["Watercraft", "Maritime"], "Subjects|Maritime|Boat"),
    "boats": ("Boats", ["Boat", "Watercraft", "Vessel"], ["Watercraft", "Maritime"], "Subjects|Maritime|Boat"),
    "sailboat": ("Sailboat", ["Boat", "Watercraft", "Vessel"], ["Watercraft", "Maritime"], "Subjects|Maritime|Sailboat"),
    "ship": ("Ship", ["Boat", "Watercraft", "Vessel"], ["Watercraft", "Maritime"], "Subjects|Maritime|Ship"),
    "bridge": ("Bridge", ["Overpass", "Span", "Infrastructure"], ["Structure", "Structures", "Architecture", "Infrastructure"], "Architecture|Infrastructure|Bridge"),
    "overpass": ("Overpass", ["Bridge", "Freeway", "Highway", "Infrastructure"], ["Structure", "Structures", "Infrastructure"], "Architecture|Infrastructure|Overpass"),
    "freeway": ("Freeway", ["Highway", "Road", "Interchange", "Infrastructure"], ["Structure", "Structures", "Infrastructure"], "Architecture|Infrastructure|Freeway"),
    "highway": ("Highway", ["Road", "Infrastructure"], ["Structure", "Structures", "Infrastructure"], "Architecture|Infrastructure|Highway"),
    "train": ("Train", ["Railroad", "Railway", "Locomotive", "Transportation"], ["Structure", "Infrastructure", "Transportation"], "Subjects|Transportation|Train"),
    "railroad": ("Railroad", ["Railway", "Train", "Tracks", "Infrastructure"], ["Structure", "Infrastructure", "Transportation"], "Architecture|Infrastructure|Railroad"),
    "oil rig": ("Oil Rig", ["Pumpjack", "Industrial", "Oil_Field"], ["Structure", "Structures", "Infrastructure", "Industrial"], "Architecture|Industrial|Oil_Rig"),
    "pumpjack": ("Pumpjack", ["Oil_Rig", "Industrial", "Oil_Field"], ["Structure", "Structures", "Infrastructure", "Industrial"], "Architecture|Industrial|Pumpjack"),
    "building": ("Building", ["Architecture"], ["Structure", "Structures", "Architecture"], "Architecture|Building"),
    "house": ("House", ["Building", "Residence"], ["Structure", "Structures", "Architecture"], "Architecture|Building|House"),
    "church": ("Church", ["Building", "Chapel"], ["Structure", "Structures", "Architecture"], "Architecture|Building|Church"),
    "door": ("Door", ["Doors", "Wooden Door", "Colonial Doors", "Entrance"], ["Structure", "Structures", "Architecture", "Building"], "Architecture|Building|Door"),
    "doors": ("Doors", ["Door", "Wooden Door", "Colonial Doors", "Entrance"], ["Structure", "Structures", "Architecture", "Building"], "Architecture|Building|Door"),
    "wooden door": ("Wooden Door", ["Door", "Doors", "Colonial Doors"], ["Structure", "Structures", "Architecture", "Building"], "Architecture|Building|Door"),
    "colonial door": ("Colonial Doors", ["Door", "Doors", "Wooden Door", "Colonial Architecture"], ["Structure", "Structures", "Architecture", "Building"], "Architecture|Colonial_Doors_And_Facades"),
    "archway": ("Archway", ["Door", "Doors", "Courtyard", "Facade"], ["Structure", "Structures", "Architecture", "Building"], "Architecture|Building|Archway"),
    "butte": ("Butte", ["Buttes", "Sandstone Butte", "Desert Monolith", "Mesa"], ["Landform", "Desert", "Rock_Formation"], "Landscape|Desert|Butte"),
    "buttes": ("Buttes", ["Butte", "Sandstone Butte", "Desert Monolith", "Mesa"], ["Landform", "Desert", "Rock_Formation"], "Landscape|Desert|Butte"),
    "mitten buttes": ("Mitten Buttes", ["Butte", "Buttes", "Sandstone Butte", "Monument Valley"], ["Landform", "Desert", "Rock_Formation"], "Landscape|Desert|Butte"),
    "car": ("Car", ["Automobile", "Vehicle"], ["Automotive", "Transportation"], "Subjects|Automotive|Car"),
    "cars": ("Cars", ["Car", "Automobile", "Vehicle"], ["Automotive", "Transportation"], "Subjects|Automotive|Car"),
    "sports car": ("Sports Car", ["Car", "Sedan", "Automobile"], ["Automotive", "Transportation"], "Subjects|Automotive|Sports_Car"),
    "sedan": ("Sedan", ["Car", "Sports Car", "Automobile"], ["Automotive", "Transportation"], "Subjects|Automotive|Sedan"),
    "lexus": ("Lexus", ["Sports Car", "Sedan", "Car", "Automobile"], ["Automotive", "Transportation"], "Subjects|Automotive|Lexus"),
    "gas station": ("Gas Station", ["Gas Pump", "Service Station", "Canopy"], ["Architecture", "Urban", "Automotive"], "Architecture|Commercial|Gas_Station"),
    "gas pump": ("Gas Pump", ["Gas Station", "Fuel Pump"], ["Architecture", "Urban", "Automotive"], "Architecture|Commercial|Gas_Pump"),
    "living room": ("Living Room", ["Indoor", "Interior", "Room"], ["Interiors", "Domestic"], "Architecture|Interiors|Living_Room"),
    "fitting room": ("Fitting Room", ["Dressing Room", "Mirror", "Indoor", "Interior"], ["Interiors", "Commercial"], "Architecture|Interiors|Fitting_Room"),
    "cat tree": ("Cat Tree", ["Scratching Post", "Pet Furniture", "Indoor"], ["Interiors", "Pets"], "Subjects|Animals|Pets|Cat_Tree"),
    "scratching post": ("Scratching Post", ["Cat Tree", "Pet Furniture", "Indoor"], ["Interiors", "Pets"], "Subjects|Animals|Pets|Scratching_Post"),
    "carpet": ("Carpet", ["Area Rug / Carpet", "Rug", "Floor"], ["Interiors", "Domestic"], "Architecture|Interiors|Carpet"),
    "area rug / carpet": ("Area Rug / Carpet", ["Carpet", "Area Rug", "Indoor"], ["Interiors", "Decor"], "Architecture|Interiors|Area_Rug_Carpet"),
    "couch": ("Couch", ["Sofa", "Furniture", "Living Room", "Indoor"], ["Interiors", "Furniture"], "Architecture|Interiors|Couch"),
    "bohemian tapestry / woven throw": ("Bohemian Tapestry / Woven Throw", ["Throw Blanket", "Tapestry", "Textiles", "Indoor"], ["Interiors", "Textiles"], "Architecture|Interiors|Bohemian_Tapestry_Throw"),
    "framed art": ("Framed Art", ["Picture Frame", "Wall Art"], ["Interiors", "Decor"], "Architecture|Interiors|Framed_Art"),
    "modern / pop wall art": ("Modern / Pop Wall Art", ["Framed Art", "Wall Art", "Indoor"], ["Interiors", "Decor"], "Architecture|Interiors|Modern_Pop_Wall_Art"),
    "decorative lamp": ("Decorative Lamp", ["Lamp", "Lighting", "Indoor"], ["Interiors", "Decor"], "Architecture|Interiors|Decorative_Lamp"),
    "center-pivot irrigation": ("Center-Pivot Irrigation", ["Circular Crop Field", "Farmland", "Agriculture"], ["Agriculture", "Aerial"], "Landscape|Agriculture|Center_Pivot_Irrigation"),
    "circular crop field": ("Circular Crop Field", ["Center-Pivot Irrigation", "Farmland", "Agriculture"], ["Agriculture", "Aerial"], "Landscape|Agriculture|Circular_Crop_Field"),
    "apricot / stone fruit orchard": ("Apricot / Stone Fruit Orchard", ["Orchard", "Farmland", "Agriculture"], ["Agriculture"], "Landscape|Agriculture|Stone_Fruit_Orchard"),
    "almond orchard": ("Almond Orchard", ["Orchard", "Farmland", "Agriculture"], ["Agriculture"], "Landscape|Agriculture|Almond_Orchard"),
    "vineyard rows": ("Vineyard Rows", ["Vineyard", "Farmland", "Agriculture"], ["Agriculture"], "Landscape|Agriculture|Vineyard_Rows"),
    "citrus grove": ("Citrus Grove", ["Orchard", "Farmland", "Agriculture"], ["Agriculture"], "Landscape|Agriculture|Citrus_Grove"),
    "wheat / grain field": ("Wheat / Grain Field", ["Farmland", "Agriculture"], ["Agriculture"], "Landscape|Agriculture|Wheat_Grain_Field"),
    "green farmland": ("Green Farmland", ["Farmland", "Agriculture"], ["Agriculture"], "Landscape|Agriculture|Green_Farmland"),
    "ploughed / fallow field": ("Ploughed / Fallow Field", ["Farmland", "Agriculture"], ["Agriculture"], "Landscape|Agriculture|Ploughed_Fallow_Field"),
    "contour farming": ("Contour Farming", ["Farmland", "Agriculture", "Rolling Hills"], ["Agriculture"], "Landscape|Agriculture|Contour_Farming"),
    "irrigation canal": ("Irrigation Canal", ["Canal", "Farmland", "Agriculture"], ["Agriculture", "Infrastructure"], "Landscape|Agriculture|Irrigation_Canal"),
    "grain silo": ("Grain Silo", ["Silo", "Barn", "Agriculture"], ["Structure", "Agriculture"], "Architecture|Ranch|Grain_Silo"),
    "tractor / combine": ("Tractor / Combine", ["Farm Machinery", "Agriculture"], ["Agriculture", "Transportation"], "Subjects|Agriculture|Tractor_Combine"),
    "highway overpass": ("Highway Overpass", ["Overpass", "Bridge", "Freeway", "Infrastructure"], ["Structure", "Infrastructure"], "Architecture|Infrastructure|Highway_Overpass"),
    "cloverleaf interchange": ("Cloverleaf Interchange", ["Highway Overpass", "Freeway", "Interchange", "Infrastructure"], ["Structure", "Infrastructure"], "Architecture|Infrastructure|Cloverleaf_Interchange"),
    "suspension bridge": ("Suspension Bridge", ["Bridge", "Infrastructure"], ["Structure", "Infrastructure"], "Architecture|Infrastructure|Suspension_Bridge"),
    "steel truss bridge": ("Steel Truss Bridge", ["Bridge", "Infrastructure"], ["Structure", "Infrastructure"], "Architecture|Infrastructure|Steel_Truss_Bridge"),
    "viaduct": ("Viaduct", ["Bridge", "Overpass", "Infrastructure"], ["Structure", "Infrastructure"], "Architecture|Infrastructure|Viaduct"),
    "skyscraper": ("Skyscraper", ["Building", "Architecture", "Cityscape"], ["Structure", "Architecture"], "Architecture|Urban|Skyscraper"),
    "glass curtain wall": ("Glass Curtain Wall", ["Skyscraper", "Building", "Architecture"], ["Structure", "Architecture"], "Architecture|Urban|Glass_Curtain_Wall"),
    "construction scaffolding": ("Construction Scaffolding", ["Building", "Construction", "Infrastructure"], ["Structure", "Infrastructure"], "Architecture|Urban|Construction_Scaffolding"),
    "amusement pier": ("Amusement Pier", ["Pier", "Coastline", "Ferris Wheel"], ["Structure", "Coast"], "Architecture|Coastal|Amusement_Pier"),
    "ferris wheel": ("Ferris Wheel", ["Amusement Pier", "Pier"], ["Structure", "Recreation"], "Architecture|Coastal|Ferris_Wheel"),
    "roller coaster": ("Roller Coaster", ["Amusement Pier", "Pier"], ["Structure", "Recreation"], "Architecture|Coastal|Roller_Coaster"),
    "shipping port / cranes": ("Shipping Port / Cranes", ["Port", "Industrial", "Maritime"], ["Structure", "Industrial"], "Architecture|Industrial|Shipping_Port_Cranes"),
    "oil derrick / pumpjack": ("Oil Derrick / Pumpjack", ["Pumpjack", "Oil Rig", "Oil Field", "Industrial"], ["Structure", "Industrial"], "Architecture|Industrial|Oil_Derrick_Pumpjack"),
    "refinery": ("Refinery", ["Oil Facility", "Industrial"], ["Structure", "Industrial"], "Architecture|Industrial|Refinery"),
    "solar farm": ("Solar Farm", ["Energy Infrastructure", "Industrial"], ["Structure", "Industrial"], "Architecture|Industrial|Solar_Farm"),
    "wind turbine": ("Wind Turbine", ["Energy Infrastructure", "Industrial"], ["Structure", "Industrial"], "Architecture|Industrial|Wind_Turbine"),
    "ferrofluid": ("Ferrofluid", ["Magnetic Spikes / Magnetism", "Macro Photography", "Science"], ["Science", "Macro"], "Subjects|Science_And_Macro|Ferrofluid"),
    "magnetic spikes / magnetism": ("Magnetic Spikes / Magnetism", ["Ferrofluid", "Macro Photography", "Science"], ["Science", "Macro"], "Subjects|Science_And_Macro|Magnetic_Spikes"),
    "macro photography": ("Macro Photography", ["Close-Up", "Studio"], ["Science", "Macro"], "Subjects|Science_And_Macro|Macro_Photography"),
    "photomicrography / microscopic": ("Photomicrography / Microscopic", ["Macro Photography", "Science"], ["Science", "Macro"], "Subjects|Science_And_Macro|Photomicrography"),
    "light refraction": ("Light Refraction", ["Optical Prism / Dispersion", "Optics", "Science"], ["Science", "Optics"], "Subjects|Science_And_Macro|Light_Refraction"),
    "optical prism / dispersion": ("Optical Prism / Dispersion", ["Light Refraction", "Optics", "Science"], ["Science", "Optics"], "Subjects|Science_And_Macro|Optical_Prism"),
    "caustics": ("Caustics", ["Light Refraction", "Optics"], ["Science", "Optics"], "Subjects|Science_And_Macro|Caustics"),
    "diffusion filter / halation": ("Diffusion Filter / Halation", ["Optics", "Lighting"], ["Science", "Optics"], "Subjects|Science_And_Macro|Diffusion_Filter"),
    "water droplet / splash": ("Water Droplet / Splash", ["Macro Photography", "Water"], ["Science", "Macro"], "Subjects|Science_And_Macro|Water_Droplet"),
    "oil and water abstract": ("Oil and Water Abstract", ["Macro Photography", "Abstract"], ["Science", "Macro"], "Subjects|Science_And_Macro|Oil_And_Water"),
    "stop motion set": ("Stop Motion Set", ["Studio", "Tabletop"], ["Studio", "Production"], "Subjects|Studio_And_Product|Stop_Motion_Set"),
    "scanography / scanner art": ("Scanography / Scanner Art", ["Studio", "Abstract"], ["Studio", "Fine_Art"], "Subjects|Studio_And_Product|Scanography"),
    "whiskey / bourbon bottle": ("Whiskey / Bourbon Bottle", ["Spirits Decanter", "Product Photography", "Bottle"], ["Studio", "Product"], "Subjects|Studio_And_Product|Whiskey_Bourbon_Bottle"),
    "spirits decanter": ("Spirits Decanter", ["Whiskey / Bourbon Bottle", "Product Photography"], ["Studio", "Product"], "Subjects|Studio_And_Product|Spirits_Decanter"),
    "rocks glass / tumbler": ("Rocks Glass / Tumbler", ["Glassware", "Product Photography"], ["Studio", "Product"], "Subjects|Studio_And_Product|Rocks_Glass_Tumbler"),
    "cosmetic lotion bottle": ("Cosmetic Lotion Bottle", ["Product Photography", "Bottle"], ["Studio", "Product"], "Subjects|Studio_And_Product|Cosmetic_Lotion_Bottle"),
    "dropper / serum bottle": ("Dropper / Serum Bottle", ["Product Photography", "Bottle"], ["Studio", "Product"], "Subjects|Studio_And_Product|Dropper_Serum_Bottle"),
    "perfume flacon": ("Perfume Flacon", ["Product Photography", "Bottle"], ["Studio", "Product"], "Subjects|Studio_And_Product|Perfume_Flacon"),
    "luxury watch": ("Luxury Watch", ["Watch", "Product Photography", "Macro Photography"], ["Studio", "Product"], "Subjects|Studio_And_Product|Luxury_Watch"),
    "sneakers": ("Sneakers", ["Footwear", "Shoes", "Apparel"], ["Personal_Storage", "Apparel"], "Subjects|Personal_And_Apparel|Sneakers"),
    "boots": ("Boots", ["Footwear", "Shoes", "Apparel"], ["Personal_Storage", "Apparel"], "Subjects|Personal_And_Apparel|Boots"),
    "dresser drawer": ("Dresser Drawer", ["Personal Storage", "Closet", "Indoor"], ["Interiors", "Personal_Storage"], "Architecture|Interiors|Dresser_Drawer"),
    "wardrobe": ("Wardrobe", ["Closet", "Personal Storage", "Indoor"], ["Interiors", "Personal_Storage"], "Architecture|Interiors|Wardrobe"),
    "adult novelty": ("Adult Novelty", ["Personal Wellness", "Intimate Wellness"], ["Personal_Storage", "Intimate_Wellness"], "Subjects|Personal_Wellness|Adult_Novelty"),
    "vibrator": ("Vibrator", ["Adult Novelty", "Personal Wellness"], ["Personal_Storage", "Intimate_Wellness"], "Subjects|Personal_Wellness|Vibrator"),
    "silicone toy": ("Silicone Toy", ["Adult Novelty", "Personal Wellness"], ["Personal_Storage", "Intimate_Wellness"], "Subjects|Personal_Wellness|Silicone_Toy"),
}

CONCEPT_PROBE_PROMPTS: Dict[str, str] = {
    "aerial_1": "high altitude aerial photography looking down from aircraft or helicopter",
    "aerial_2": "bird's eye view aerial landscape from plane",
    "terrestrial_1": "ground level terrestrial landscape or eye-level photography",
    "terrestrial_2": "eye-level photograph of ranch, barn, mountains, trees, wildlife, or person",
    "person": "portrait of a person, human, man, woman, or family",
    "person_2": "a photograph showing a person, man, woman, or photographer",
    "male": "a photograph of a man, male person, cowboy, or male photographer",
    "female": "a photograph of a woman, female person, or girl",
    "photographer": "a photographer holding a camera or taking a photo",
    "bison": "a photograph of american bison or buffalo",
    "horse": "a photograph of a horse or horses",
    "cattle": "a photograph of cattle, cows, or bull",
    "bird": "a photograph of a bird, pelican, eagle, hawk, heron, crane, or waterfowl",
    "dog": "a photograph of a dog",
    "wildlife": "a photograph of a wild animal or wildlife in nature",
    "taft": "aerial view of dense oil field with pumpjacks, steam pipes, and dirt roads in Taft California",
    "palouse": "aerial view of smooth rolling green and gold wheat hills in the Palouse Washington",
    "bg_landscape": "a general scenic landscape of mountains, rocks, water, or trees without people or animals",
    # Global Landmark Gazetteer Zero-Shot Probes
    "lm_hallgrimskirkja": "Hallgrimskirkja church tower in Reykjavik Iceland with stepped concrete wings",
    "lm_kirkjufell": "Kirkjufell cone-shaped mountain peak and Kirkjufellsfoss waterfall in Snaefellsnes Iceland",
    "lm_jokulsarlon": "Jokulsarlon glacial lagoon and Diamond Beach translucent blue icebergs on black volcanic sand in Iceland",
    "lm_reynisfjara": "Reynisfjara black sand beach and Reynisdrangar basalt sea stacks and columns in Vik Iceland",
    "lm_gullfoss": "Gullfoss waterfall and dramatic Icelandic waterfall canyon over volcanic basalt cliffs in Iceland",
    "lm_valley_of_gods": "Valley of the Gods isolated red sandstone buttes, spires, and monoliths in southern Utah",
    "lm_monument_valley": "Monument Valley iconic red sandstone Mitten Buttes and desert mesas in Arizona and Utah",
    "lm_castleton_fisher": "Castleton Tower and Fisher Towers red sandstone monolith spires in Castle Valley Moab Utah",
    "lm_devils_tower": "Devils Tower monolithic volcanic phonolite column butte rising above trees in Wyoming",
    "lm_grand_tetons": "Grand Teton jagged alpine mountain peaks rising above Jackson Hole and Snake River in Wyoming",
    "lm_mount_rainier": "Mount Rainier glaciated volcanic mountain peak in Cascade Range Washington",
    "lm_yosemite": "Yosemite Valley granite cliffs Half Dome and El Capitan in Sierra Nevada California",
    "lm_mono_lake": "Mono Lake limestone tufa towers rising from alkaline lake in Eastern Sierra California",
    "lm_washington_monument": "Washington Monument white marble obelisk surrounded by circle of American flags in Washington DC",
    "lm_chicago": "Chicago downtown skyscraper skyline with Willis Sears Tower along Lake Michigan in Illinois",
    "lm_venice_italy": "Venice Italy Grand Canal historic Venetian buildings, bridges, boats, and gondolas",
    "lm_colonial_doors": "rustic weathered colonial wooden doors and colorful stucco wall or courtyard in San Miguel de Allende Oaxaca Mexico",
    "lm_highway_interchange": "aerial view of concrete highway interchange freeway overpass asphalt road ramps traffic infrastructure",
    # --- 5-FACET VISUAL KEYWORD PROBES ---
    "f1_mountain_peak": "rugged mountain peaks, alpine ridge, or jagged mountain range",
    "f1_canyon_mesa": "red rock canyon walls, sandstone mesa, desert gorge, or eroded badlands",
    "f1_coastline_surf": "ocean coastline, rocky shore, sandy beach, sea cliffs, or coastal surf",
    "f1_river_waterway": "flowing river, braided river channels, winding stream, or marsh waterway",
    "f1_lake_lagoon": "calm alpine lake, desert lake reflection, lagoon, or open water basin",
    "f1_forest_woods": "dense forest trees, woodland grove, autumn aspen trees, or conifer canopy",
    "f1_desert_arid": "arid desert landscape, sand dunes, desert valley, or scrubland",
    "f1_ranch_pasture": "rural ranch pasture, agricultural farmland fields, meadow, or prairie",
    "f1_barn_farmstead": "rustic wooden barn, ranch homestead, cabin, or agricultural building",
    "f1_colonial_facade": "historic colonial building facade, painted stucco wall, or masonry architecture",
    "f1_industrial_facility": "industrial facility, oil refinery, storage tanks, pipelines, or energy infrastructure",
    "f1_urban_skyline": "city skyline, urban buildings, downtown architecture, or monument",
    "f2_doors_windows": "wooden doors, entrance doorway, window shutters, wrought iron grille, or architectural portal",
    "f2_archway_courtyard": "stone or stucco archway, colonnade, courtyard, or veranda",
    "f2_fence_corral": "wooden ranch fence, fence posts, corral rails, or wire fence line",
    "f2_bridge_pier": "bridge span, wooden pier, boardwalk, jetty, or overpass structure",
    "f2_boats_vessels": "boats, sailboats, barges, ships, or watercraft on the water",
    "f2_rock_outcrop": "weathered rock outcrops, boulder field, cliff face, or stone ledges",
    "f2_foreground_flora": "wildflowers, desert cactus, tall meadow grass, or foreground foliage",
    "f2_water_reflection": "mirror water reflection, breaking ocean waves, whitewater foam, or wet shoreline",
    "f2_road_pathway": "winding road, dirt track, highway pavement, or mountain trail",
    "f2_clouds_sky": "cumulus clouds, dramatic storm clouds, clear sky horizon, or cloud formations",
    "f2_snow_ice": "snow-covered slopes, winter snowpack, frost, or glacial ice",
    "f3_mat_wood": "weathered timber wood grain, rustic wooden boards, or aged barn wood texture",
    "f3_mat_stucco_masonry": "textured painted stucco wall, plaster, adobe brick, or carved masonry stone",
    "f3_mat_natural_stone": "stratified sandstone layers, granite rock face, volcanic basalt, or rugged cliff stone",
    "f3_mat_metal_steel": "rusted iron metal, steel structural trusses, industrial piping, or metallic surface",
    "f3_mat_water_ice": "liquid water surface, translucent ice, ocean spray, or wet reflective sand",
    "f3_mat_earth_sand": "textured desert sand, plowed agricultural soil, gravel earth, or mudflats",
    "f3_col_vibrant": "vibrant saturated colors, bold rich chromatic contrast, and vivid color palette",
    "f3_col_warm_golden": "warm golden amber, ochre, terracotta, and sunlit earth tones",
    "f3_col_muted_earth": "muted natural earth tones, sage green, weathered brown, and subtle neutral palette",
    "f3_col_cool_blue": "cool cerulean blue, slate gray, icy cyan, and crisp atmospheric tones",
    "f4_comp_centered": "centered symmetrical composition or straight-on frontal architectural framing",
    "f4_comp_tight_detail": "tight close-up architectural detail, intimate subject study, or texture frame",
    "f4_comp_wide_vista": "wide expansive panoramic landscape vista with deep horizon depth",
    "f4_comp_leading_lines": "strong diagonal leading lines, S-curve river or road, or receding perspective",
    "f4_comp_overhead_grid": "abstract overhead geometric pattern or high-angle topographic texture",
    "f4_comp_layered_depth": "layered foreground, midground, and background depth in natural landscape",
    "f5_light_golden_hour": "warm golden hour sunlight at sunrise or sunset with long directional shadows",
    "f5_light_soft_overcast": "soft diffused overcast light with gentle even illumination",
    "f5_light_crisp_daylight": "bright crisp daylight sun with clear atmospheric visibility and sharp shadows",
    "f5_light_dramatic_storm": "dramatic storm light, chiaroscuro contrast, or sunbeams breaking through dark clouds",
    "f5_light_mist_haze": "morning mist, atmospheric valley haze, coastal fog, or soft twilight glow",
    # --- CONTRASTIVE HABITAT & ARTIFACT FOIL PROBES (High-Tension Object Gating) ---
    "frog": "a close-up photograph of a live frog, toad, or amphibian",
    "cat": "a photograph of a live domestic cat, kitten, or feline",
    "deer_elk": "a photograph of a live deer, mule deer, elk, moose, or pronghorn antelope",
    "bear": "a photograph of a live bear or grizzly bear",
    "car_vehicle": "a photograph of a car, truck, classic automobile, or motor vehicle",
    "train_rail": "a photograph of a train locomotive or railway cars on tracks",
    "airplane": "a photograph of an airplane, aircraft, or helicopter",
    "foil_empty_forest_path": "empty forest trail, woodland pathway, tree trunks, branches, leaves, and shadows with no people and no animals",
    "foil_empty_trees_sky": "empty tree branches, foliage, bushes, grass, or sky with no birds and no wildlife",
    "foil_wet_rocks_moss": "wet rocks, pebbles, moss, fallen logs, mud, or pond water surface with no frogs and no animals",
    "foil_empty_water_pond": "empty pond, lake reflection, river water, shoreline, reeds, or ranch pasture with no boats and no watercraft",
    "foil_empty_ranch_barn": "empty ranch pasture, wooden barn, corral fence, dirt road, or hay field with no horses, no cattle, and no people",
    "foil_empty_desert_rocks": "empty desert rock formations, sandstone cliffs, boulders, or mountain slopes with no people and no animals",
    "foil_statue_sculpture": "an inanimate statue, stone or bronze sculpture, wooden carving, mannequin, decoy, or monument",
    "foil_framed_picture_wall": "a framed photograph hanging on a wall, painting, canvas print, mural, poster, or interior wall art",
    # --- SCENE ROUTER & EVERYDAY / INDOOR / AUTOMOTIVE / PORTRAIT PROBES ---
    "scene_indoor_domestic": "an indoor room inside a house, apartment, living room, bedroom, or domestic interior",
    "scene_mirror_selfie": "a person taking a mirror selfie holding a smartphone in front of a mirror indoors",
    "scene_urban_automotive": "an urban street, parking lot, gas station, or automobile outdoors",
    "scene_outdoor_nature": "an outdoor natural landscape of mountains, forest, desert, ocean, or rural countryside",
    "dog_indoor": "a small tan and white dog, chihuahua mix, or puppy lying on a rug or carpet indoors",
    "cat_indoor": "a domestic cat sitting on a cat tree or furniture indoors",
    "cat_tree": "a carpeted cat tree, cat tower, or scratching post indoors",
    "living_room": "an indoor living room with sofa, area rug, carpet, and window",
    "framed_art": "framed art or picture frame hanging on an interior wall",
    "mirror_selfie": "a mirror selfie of a person holding a smartphone in front of a mirror",
    "fitting_room": "a clothing store fitting room or dressing room with a mirror",
    "sports_car_sedan": "a modern sports sedan, luxury car, or Lexus automobile parked at a gas station or street",
    "gas_station": "a gas station canopy with fuel pumps and overhead lights",
    "light_night_artificial": "nighttime photograph with dark night sky illuminated by bright artificial canopy or street lights",
    "light_daylight_midday": "bright sunny daytime photograph under natural midday blue sky",
    "foil_empty_room_carpet": "an empty carpet, rug, floor, or empty living room furniture with no dog and no cat",
    # --- v4.0 LOCAL CROP FOILS (Per-Crop Local Foil Tension) ---
    "foil_blanket_pillow_fabric": "folded throw blanket, woven bohemian tapestry fabric, patterned pillow, bedspread, or upholstery textile with no cat and no dog",
    "foil_crumpled_clothing": "crumpled clothing, folded shirts, laundry fabric, towels, or cloth material with no animal and no pet",
    "foil_empty_furniture_wall": "empty sofa, empty couch cushion, empty carpet floor, plain interior wall, baseboard, or empty room corner with no pet and no person",
}

# --- v4.0 PASS 1: MACRO SCENE BIOME LOCK & STRICT MUTUAL-EXCLUSION GATES ---
MACRO_BIOME_DEFINITIONS: Dict[str, Dict[str, Any]] = {
    "Coastal / Beach & Pier": {
        "prompts": [
            "coastal ocean beach, coastline, sea, breaking waves, shoreline, beach pier, sand, tidal pools, or seaside boardwalk",
            "outdoor ocean coastline with surf, breakwater, coastal bluffs, sand beach, pier, and marine horizon",
        ],
        "forbidden_tags_lower": {
            "desert", "deserts", "sand dunes", "dune", "dunes", "canyon", "canyons", "butte", "buttes",
            "badlands", "mesa", "mesas", "indoor", "living room", "couch", "cat tree", "bedroom",
            "dresser drawer", "wardrobe", "alligator", "bison", "buffalo", "bear", "grizzly bear",
            "center-pivot irrigation", "circular crop field", "tractor / combine", "combine",
            "wheat field", "corn field", "silo", "grain silo", "palouse", "mountain range",
            "alpine mountain", "glacier", "adult novelty", "vibrator",
            "cat", "cats", "kitten", "scottish fold", "domestic cat", "house pet", "pets", "pet", "pets", "pet",
            "scratching post", "litter box", "dog", "dogs", "puppy", "chihuahua", "french bulldog",
        },
        "allowed_domains": {
            "coastal", "ornithology_wildlife", "civil_infrastructure", "flora_trees", "people",
        },
    },
    "Urban / Downtown & Infrastructure": {
        "prompts": [
            "an urban downtown city skyline, skyscrapers, modern glass buildings, bridges, highway overpass, streets, or metropolitan infrastructure",
            "architecture, city buildings, streets, commercial district, suspension bridge, freeway interchange, or urban transit",
        ],
        "forbidden_tags_lower": {
            "agriculture", "farmland", "rolling farmland", "wheat field", "corn field", "center-pivot irrigation",
            "circular crop field", "tractor / combine", "grain silo", "silo", "palouse", "desert",
            "sand dunes", "canyon", "canyons", "butte", "buttes", "mountain range", "alpine mountain",
            "glacier", "alligator", "bison", "buffalo", "bear", "whale", "dolphin", "adult novelty",
            "vibrator", "cat tree", "scratching post", "litter box", "dresser drawer", "wardrobe",
            "cat", "cats", "kitten", "scottish fold", "domestic cat", "house pet", "pets", "pet",
        },
        "allowed_domains": {
            "civil_infrastructure", "urban_automotive", "people",
        },
    },
    "Agricultural / Rolling Farmland": {
        "prompts": [
            "agricultural farmland, rolling green and gold hills, crop fields, wheat fields, farm, barn, silo, tractor, or ploughed earth",
            "scenic rural farming landscape with rolling hills, cultivated fields, farmsteads, and agricultural terrain",
        ],
        "forbidden_tags_lower": {
            "desert", "deserts", "sand dunes", "dune", "dunes", "canyon", "canyons", "butte", "buttes",
            "badlands", "mountain range", "alpine mountain", "glacier", "snowy peak", "ocean", "beach",
            "coastline", "pier", "surf", "coral reef", "alligator", "whale", "dolphin", "seal", "sea lion",
            "cat tree", "couch", "living room", "dresser drawer", "wardrobe", "adult novelty", "vibrator",
            "cat", "cats", "kitten", "scottish fold", "domestic cat", "house pet", "pets", "pet", "pets", "pet",
            "scratching post", "litter box", "dog", "dogs", "puppy", "chihuahua", "french bulldog",
        },
        "allowed_domains": {
            "aerial_agriculture", "flora_trees", "equine", "civil_infrastructure",
        },
    },
    "Desert / Canyon & Badlands": {
        "prompts": [
            "arid desert landscape, sandstone canyon, red rock buttes, mesas, badlands, dry washes, or desert dunes",
            "scenic desert southwest with canyon walls, sandstone buttes, rocky red cliffs, and arid desert terrain",
        ],
        "forbidden_tags_lower": {
            "ocean", "breaking waves", "surf", "coral reef", "beach pier", "boardwalk", "tidal pool",
            "rainforest", "cypress swamp", "bayou", "swamp", "alligator", "whale", "dolphin", "sea otter",
            "seal", "sea lion", "living room", "cat tree", "couch", "dresser drawer", "wardrobe",
            "adult novelty", "vibrator",
            "cat", "cats", "kitten", "scottish fold", "domestic cat", "house pet", "pets", "pet", "pets", "pet",
            "scratching post", "litter box", "dog", "dogs", "puppy", "chihuahua", "french bulldog",
        },
        "allowed_domains": {
            "ornithology_wildlife", "flora_trees", "civil_infrastructure",
        },
    },
    "Alpine / Mountain & Forest": {
        "prompts": [
            "alpine mountain range, snow-capped rocky peaks, high altitude mountain valley, glacial lake, or evergreen pine forest",
            "scenic high mountains with alpine ridges, evergreen conifer forest, mountain peaks, and alpine wilderness",
        ],
        "forbidden_tags_lower": {
            "sand dunes", "dune", "dunes", "desert", "beach pier", "boardwalk", "coral reef",
            "center-pivot irrigation", "circular crop field", "oil derrick / pumpjack", "pumpjack",
            "refinery", "skyscraper", "highway overpass", "cloverleaf interchange", "cat tree",
            "dresser drawer", "wardrobe", "alligator", "adult novelty", "vibrator",
            "cat", "cats", "kitten", "scottish fold", "domestic cat", "house pet", "pets", "pet", "pets", "pet",
            "scratching post", "litter box", "dog", "dogs", "puppy", "chihuahua", "french bulldog",
        },
        "allowed_domains": {
            "ornithology_wildlife", "flora_trees", "civil_infrastructure",
        },
    },
    "Indoor / Residential & Living Space": {
        "prompts": [
            "an indoor living room, bedroom, apartment, or house interior with sofa, couch, bed, area rug, carpet, or cat tree",
            "an indoor domestic home room with furniture, lamps, throw blanket, framed wall art, and houseplants",
        ],
        "forbidden_tags_lower": {
            "alligator", "bison", "buffalo", "american bison", "bear", "grizzly bear", "grizzly / black bear",
            "whale", "humpback whale", "dolphin", "seal", "sea lion", "seal / sea lion", "sea otter",
            "pelican", "pelicans", "brown pelican", "great blue heron", "heron", "snowy egret", "egret",
            "sandhill crane", "crane", "avocet", "cormorant", "seagull", "gull", "bald eagle", "eagle",
            "red-tailed hawk", "hawk", "osprey", "great horned owl", "owl", "mallard", "canada goose",
            "goose", "geese", "snow geese", "duck", "ducks", "waterfowl", "frog", "frogs", "toad",
            "elk", "mule deer", "deer", "moose", "bighorn sheep", "pronghorn", "antelope", "coyote",
            "wolf", "red fox", "fox", "horse", "horses", "quarter horse", "mustang", "cattle", "cow", "cows",
            "canyon", "canyons", "butte", "buttes", "mitten buttes", "highway overpass", "overpass",
            "cloverleaf interchange", "suspension bridge", "steel truss bridge", "viaduct",
            "center-pivot irrigation", "circular crop field", "oil derrick / pumpjack", "pumpjack",
            "oil rig", "refinery", "solar farm", "wind turbine", "grain silo", "silo", "tractor / combine",
            "tractor", "combine", "mountain range", "mountains", "mountain", "sand dunes", "desert", "highway", "freeway",
        },
        "allowed_domains": {
            "feline", "canine", "people", "indoor_decor_textiles", "indoor_flora", "studio_product",
        },
    },
    "Indoor / Closet, Drawer & Personal Storage": {
        "prompts": [
            "inside an indoor closet, wardrobe, dresser drawer, shelf, or personal storage compartment",
            "a close-up inside a bedroom drawer, closet shelf, shoe rack, or personal storage space",
        ],
        "forbidden_tags_lower": {
            "architecture", "building", "buildings", "industrial storage", "industrial", "industrial facility",
            "skyscraper", "glass curtain wall", "construction scaffolding", "bridge", "highway overpass",
            "overpass", "alligator", "bison", "buffalo", "bear", "grizzly / black bear", "whale",
            "humpback whale", "pelican", "brown pelican", "frog", "frogs", "canyon", "butte", "buttes",
            "mountain", "mountains", "horse", "horses", "cattle", "cow", "cows", "sand dunes", "desert", "highway", "freeway",
        },
        "allowed_domains": {
            "closet_storage_wellness", "feline", "canine", "people", "studio_product",
        },
    },
    "Studio / Tabletop, Product & Scientific Macro": {
        "prompts": [
            "a studio tabletop product photograph of a bottle, wine bottle, wine glasses on a wine barrel, spirits decanter, glass tumbler, cosmetic bottle, or luxury watch",
            "a studio macro or optical physics photograph of a translucent glass sculpture, crystal figurine on a pitch black background, ferrofluid, magnetic spikes, light refraction prism, caustics, or water droplets",
            "a close-up culinary, winery, or tabletop still-life photograph of wine tasting glasses, vineyard bottles, gourmet food, or art glass isolated on a dark studio backdrop",
            "an extreme scientific macro or focus-stacked photograph of an insect, bee, honeybee head, compound eyes, crystalline facets, or photomicrography",
        ],
        "forbidden_tags_lower": {
            "alligator", "bison", "buffalo", "bear", "whale", "pelican", "frog", "frogs",
            "canyon", "butte", "buttes", "highway overpass", "center-pivot irrigation",
            "mountain range", "mountains", "mountain", "sand dunes", "desert", "highway", "freeway",
        },
        "allowed_domains": {
            "science_macro_optical", "studio_product", "closet_storage_wellness", "indoor_flora", "people",
        },
    },
    "Portrait / Mirror & People": {
        "prompts": [
            "a portrait of a person, man, woman, group photo, event gathering, winery tasting guests, or mirror selfie holding a smartphone in front of a mirror",
            "a close-up or medium portrait of people, woman in a dress with necklace, friends, family, or photographer",
        ],
        "forbidden_tags_lower": {
            "alligator", "bison", "buffalo", "whale", "humpback whale", "frog", "frogs",
            "center-pivot irrigation", "circular crop field", "oil derrick / pumpjack", "sand dunes", "desert",
            "mountain range", "mountains", "mountain", "canyon", "canyons", "butte", "buttes", "highway overpass", "overpass", "highway", "freeway",
        },
        "allowed_domains": {
            "people", "feline", "canine", "indoor_decor_textiles", "closet_storage_wellness", "studio_product",
        },
    },
    "Urban / Automotive, Bridges & Architecture": {
        "prompts": [
            "an urban street, car, sports sedan, gas station, city buildings, skyscraper, bridge, or highway overpass",
            "architecture, historic colonial doors, urban infrastructure, train tracks, or modern buildings",
        ],
        "forbidden_tags_lower": {
            "alligator", "bison", "buffalo", "whale", "humpback whale", "frog", "frogs",
            "adult novelty", "vibrator", "silicone toy", "cat tree", "scratching post", "litter box",
        },
        "allowed_domains": {
            "civil_infrastructure", "urban_automotive", "people",
        },
    },
    "Aerial / Agriculture, Infrastructure & Topo": {
        "prompts": [
            "high altitude aerial photography looking down from an aircraft at farmland, circular crop fields, orchards, rivers, or oil fields",
            "bird's-eye view aerial landscape of agricultural fields, highway interchanges, coastlines, or topographic terrain",
        ],
        "forbidden_tags_lower": {
            "cat", "cats", "kitten", "scottish fold", "domestic cat", "house pet", "pets", "pet", "pets", "pet",
            "dog", "dogs", "puppy", "chihuahua", "french bulldog", "cat tree", "scratching post", "litter box",
            "couch", "living room", "bohemian tapestry / woven throw",
            "framed art", "adult novelty", "vibrator", "silicone toy", "frog", "frogs", "dresser drawer", "wardrobe",
        },
        "allowed_domains": {
            "aerial_agriculture", "civil_infrastructure", "ornithology_wildlife", "flora_trees", "equine",
        },
    },
    "Outdoor / Wilderness, Ranch, Coastal & Flora": {
        "prompts": [
            "an outdoor natural landscape of mountains, canyon, desert buttes, forest trees, river, coastline, beach, or rural ranch pasture",
            "outdoor nature photography of wildlife, birds, horses, cattle, wildflowers, trees, rocks, or ocean surf",
        ],
        "forbidden_tags_lower": {
            "adult novelty", "vibrator", "silicone toy", "dresser drawer", "wardrobe", "cat tree", "fitting room",
        },
        "allowed_domains": {
            "ornithology_wildlife", "flora_trees", "equine", "civil_infrastructure", "feline", "canine", "people",
        },
    },
}

# --- v4.0 PASS 3: MULTI-PROMPT ENSEMBLE ANCHORS (Computed Once at Startup, 0ms Runtime Overhead) ---
MULTI_PROMPT_PARENT_ENSEMBLES: Dict[str, List[str]] = {
    "cat": [
        "a photograph of a live domestic cat, kitten, or housecat",
        "an indoor sleeping cat curled up on a bed, sofa, couch, pillow, or blanket",
        "close-up of domestic feline fur, plush grey-brown or tabby cat coat, cat ears, whiskers, nose, or paws",
        "a domestic cat sitting or lounging on a carpeted cat tree tower or scratching post indoors",
        "a plush grey-brown Scottish Fold or British Shorthair cat indoors",
    ],
    "dog": [
        "a photograph of a live domestic dog, puppy, or canine companion",
        "a small tan and white dog, Chihuahua, or Rat Terrier standing or lying on a rug or carpet indoors",
        "a white French Bulldog or compact muscular dog with bat ears indoors",
        "a domestic dog looking at the camera inside a living room or outdoors",
    ],
    "person": [
        "a portrait of a person, human, man, woman, or family",
        "a person taking a mirror selfie holding a smartphone in front of a mirror",
        "a candid photograph of a man, woman, friend, or photographer",
    ],
    "cat_tree": [
        "a carpeted cat tree tower, multi-level cat condo, or sisal scratching post indoors",
        "a plush beige or grey pet cat tree platform by a living room couch or window",
    ],
    "couch": [
        "an indoor living room couch, upholstered sofa, or sectional sofa with cushions",
        "a domestic sofa or couch inside a home living space",
    ],
    "bohemian_throw": [
        "a patterned bohemian tapestry throw blanket or woven decorative throw draped over a couch or bed",
        "a colorful woven textile blanket or patterned throw fabric on indoor furniture",
    ],
    "area_rug": [
        "an indoor area rug, woven floor rug, or domestic living room carpet",
        "a patterned rug or carpet on an indoor floor",
    ],
    "framed_art": [
        "framed wall art, picture frames, or gallery prints hanging on an interior living room wall",
        "modern pop wall art or framed illustration mounted on an indoor wall",
    ],
    "decorative_lamp": [
        "an indoor decorative table lamp, floor lamp, or modern accent lighting fixture in a room",
    ],
}

# --- v4.0 PASS 3: SPECIALIST DRILL-DOWN MATRIX ---
# Maps each specialist tag -> {domain, parent, hierarchy, prompts, min_cos, margin}
SPECIALIST_DRILLDOWN_TAXONOMY: List[Dict[str, Any]] = [
    # 1. Feline (Cat / Kitten)
    {"tag": "Scottish Fold", "domain": "feline", "parent": "Cat", "hierarchy": "Subjects|Animals|Pets|Cat|Scottish_Fold", "min_cos": 0.235, "prompts": [
        "a plush grey-brown or blue-grey Scottish Fold cat with folded ears and round face",
        "a dense plush grey-brown shorthair cat with small folded ears lounging on a cat tree or bed",
        "close-up of plush grey-brown Scottish Fold cat fur, paws, whiskers, or round head",
    ]},
    {"tag": "British Shorthair", "domain": "feline", "parent": "Cat", "hierarchy": "Subjects|Animals|Pets|Cat|British_Shorthair", "min_cos": 0.250, "prompts": [
        "a solid blue-grey British Shorthair cat with upright ears and copper eyes",
    ]},
    {"tag": "American Shorthair", "domain": "feline", "parent": "Cat", "hierarchy": "Subjects|Animals|Pets|Cat|American_Shorthair", "min_cos": 0.250, "prompts": [
        "an American Shorthair domestic cat with classic striped coat",
    ]},
    {"tag": "Tabby Cat", "domain": "feline", "parent": "Cat", "hierarchy": "Subjects|Animals|Pets|Cat|Tabby_Cat", "min_cos": 0.245, "prompts": [
        "a striped brown or grey mackerel tabby cat with M forehead markings",
    ]},
    {"tag": "Orange Tabby", "domain": "feline", "parent": "Cat", "hierarchy": "Subjects|Animals|Pets|Cat|Orange_Tabby", "min_cos": 0.250, "prompts": [
        "a ginger orange tabby cat or marmalade cat with orange striped fur",
    ]},
    {"tag": "Black Cat", "domain": "feline", "parent": "Cat", "hierarchy": "Subjects|Animals|Pets|Cat|Black_Cat", "min_cos": 0.250, "prompts": [
        "a solid black domestic cat with sleek black fur",
    ]},
    {"tag": "Tuxedo Cat", "domain": "feline", "parent": "Cat", "hierarchy": "Subjects|Animals|Pets|Cat|Tuxedo_Cat", "min_cos": 0.250, "prompts": [
        "a black and white bicolor tuxedo cat with white chest and paws",
    ]},
    {"tag": "Calico", "domain": "feline", "parent": "Cat", "hierarchy": "Subjects|Animals|Pets|Cat|Calico", "min_cos": 0.250, "prompts": [
        "a tri-color calico cat with white, orange, and black patches",
    ]},
    {"tag": "Tortoiseshell", "domain": "feline", "parent": "Cat", "hierarchy": "Subjects|Animals|Pets|Cat|Tortoiseshell", "min_cos": 0.250, "prompts": [
        "a mottled tortoiseshell cat with brindled black and orange fur",
    ]},
    {"tag": "Siamese", "domain": "feline", "parent": "Cat", "hierarchy": "Subjects|Animals|Pets|Cat|Siamese", "min_cos": 0.255, "prompts": [
        "a sleek cream Siamese cat with dark seal point face, ears, and blue eyes",
    ]},
    {"tag": "Ragdoll", "domain": "feline", "parent": "Cat", "hierarchy": "Subjects|Animals|Pets|Cat|Ragdoll", "min_cos": 0.255, "prompts": [
        "a fluffy longhaired Ragdoll cat with blue eyes and colorpoint coat",
    ]},
    {"tag": "Maine Coon / Longhair", "domain": "feline", "parent": "Cat", "hierarchy": "Subjects|Animals|Pets|Cat|Maine_Coon", "min_cos": 0.255, "prompts": [
        "a large fluffy Maine Coon or domestic longhair cat with tufted ears and bushy tail",
    ]},
    {"tag": "Bengal", "domain": "feline", "parent": "Cat", "hierarchy": "Subjects|Animals|Pets|Cat|Bengal", "min_cos": 0.255, "prompts": [
        "a spotted rosette Bengal cat with leopard-like markings",
    ]},
    {"tag": "Persian", "domain": "feline", "parent": "Cat", "hierarchy": "Subjects|Animals|Pets|Cat|Persian", "min_cos": 0.255, "prompts": [
        "a flat-faced longhaired Persian cat with luxurious fluffy coat",
    ]},
    {"tag": "Cat Tree", "domain": "indoor_decor_textiles", "parent": "Cat Tree", "hierarchy": "Subjects|Animals|Pets|Cat_Tree", "min_cos": 0.235, "prompts": [
        "a carpeted cat tree tower, multi-level cat condo, or sisal scratching post indoors",
    ]},
    {"tag": "Scratching Post", "domain": "indoor_decor_textiles", "parent": "Cat Tree", "hierarchy": "Subjects|Animals|Pets|Scratching_Post", "min_cos": 0.245, "prompts": [
        "a sisal rope cat scratching post or carpeted scratching pole",
    ]},

    # 2. Canine (Dog / Puppy)
    {"tag": "Chihuahua", "domain": "canine", "parent": "Dog", "hierarchy": "Subjects|Animals|Pets|Dog|Chihuahua", "min_cos": 0.240, "prompts": [
        "a small tan and white Chihuahua or Chihuahua mix dog with large upright ears",
    ]},
    {"tag": "Rat Terrier", "domain": "canine", "parent": "Dog", "hierarchy": "Subjects|Animals|Pets|Dog|Rat_Terrier", "min_cos": 0.240, "prompts": [
        "a small sleek tan and white Rat Terrier or feist dog with upright ears",
    ]},
    {"tag": "Jack Russell Terrier", "domain": "canine", "parent": "Dog", "hierarchy": "Subjects|Animals|Pets|Dog|Jack_Russell_Terrier", "min_cos": 0.245, "prompts": [
        "a small white and tan Jack Russell Terrier dog",
    ]},
    {"tag": "French Bulldog", "domain": "canine", "parent": "Dog", "hierarchy": "Subjects|Animals|Pets|Dog|French_Bulldog", "min_cos": 0.240, "prompts": [
        "a compact muscular French Bulldog with large upright bat ears and flat snout",
        "a white or cream French Bulldog sitting indoors",
    ]},
    {"tag": "English Bulldog", "domain": "canine", "parent": "Dog", "hierarchy": "Subjects|Animals|Pets|Dog|English_Bulldog", "min_cos": 0.250, "prompts": [
        "a stocky wrinkled English Bulldog with heavy jowls",
    ]},
    {"tag": "Corgi", "domain": "canine", "parent": "Dog", "hierarchy": "Subjects|Animals|Pets|Dog|Corgi", "min_cos": 0.250, "prompts": [
        "a short-legged Pembroke Welsh Corgi dog with fox-like face",
    ]},
    {"tag": "Dachshund", "domain": "canine", "parent": "Dog", "hierarchy": "Subjects|Animals|Pets|Dog|Dachshund", "min_cos": 0.250, "prompts": [
        "a long-bodied short-legged Dachshund wiener dog",
    ]},
    {"tag": "Beagle", "domain": "canine", "parent": "Dog", "hierarchy": "Subjects|Animals|Pets|Dog|Beagle", "min_cos": 0.250, "prompts": [
        "a tricolor hound Beagle dog with floppy ears",
    ]},
    {"tag": "Golden Retriever", "domain": "canine", "parent": "Dog", "hierarchy": "Subjects|Animals|Pets|Dog|Golden_Retriever", "min_cos": 0.250, "prompts": [
        "a long-coated golden yellow Golden Retriever dog",
    ]},
    {"tag": "Labrador Retriever", "domain": "canine", "parent": "Dog", "hierarchy": "Subjects|Animals|Pets|Dog|Labrador_Retriever", "min_cos": 0.250, "prompts": [
        "a short-coated yellow, black, or chocolate Labrador Retriever dog",
    ]},
    {"tag": "German Shepherd", "domain": "canine", "parent": "Dog", "hierarchy": "Subjects|Animals|Pets|Dog|German_Shepherd", "min_cos": 0.250, "prompts": [
        "a tan and black German Shepherd dog with pointed ears",
    ]},
    {"tag": "Australian Shepherd", "domain": "canine", "parent": "Dog", "hierarchy": "Subjects|Animals|Pets|Dog|Australian_Shepherd", "min_cos": 0.250, "prompts": [
        "a fluffy merle Australian Shepherd herding dog",
    ]},
    {"tag": "Border Collie", "domain": "canine", "parent": "Dog", "hierarchy": "Subjects|Animals|Pets|Dog|Border_Collie", "min_cos": 0.250, "prompts": [
        "a black and white Border Collie herding dog",
    ]},
    {"tag": "Poodle / Doodle", "domain": "canine", "parent": "Dog", "hierarchy": "Subjects|Animals|Pets|Dog|Poodle_Doodle", "min_cos": 0.250, "prompts": [
        "a curly-coated Poodle, Goldendoodle, or Labradoodle dog",
    ]},
    {"tag": "Siberian Husky", "domain": "canine", "parent": "Dog", "hierarchy": "Subjects|Animals|Pets|Dog|Siberian_Husky", "min_cos": 0.250, "prompts": [
        "a thick-coated Siberian Husky or Alaskan Malamute dog with wolf-like markings",
    ]},
    {"tag": "Boxer", "domain": "canine", "parent": "Dog", "hierarchy": "Subjects|Animals|Pets|Dog|Boxer", "min_cos": 0.250, "prompts": [
        "a muscular fawn and white Boxer dog with square jaw",
    ]},
    {"tag": "Pit Bull Terrier", "domain": "canine", "parent": "Dog", "hierarchy": "Subjects|Animals|Pets|Dog|Pit_Bull_Terrier", "min_cos": 0.250, "prompts": [
        "a muscular short-haired American Pit Bull Terrier or Staffordshire Terrier dog",
    ]},
    {"tag": "Pomeranian", "domain": "canine", "parent": "Dog", "hierarchy": "Subjects|Animals|Pets|Dog|Pomeranian", "min_cos": 0.250, "prompts": [
        "a tiny fluffy Pomeranian toy dog",
    ]},
    {"tag": "Spaniel", "domain": "canine", "parent": "Dog", "hierarchy": "Subjects|Animals|Pets|Dog|Spaniel", "min_cos": 0.250, "prompts": [
        "a Cocker Spaniel, Cavalier King Charles Spaniel, or Springer Spaniel with long wavy ears",
    ]},

    # 3. Equine (Horse)
    {"tag": "Mustang", "domain": "equine", "parent": "Horse", "hierarchy": "Subjects|Animals|Horses|Mustang", "min_cos": 0.245, "prompts": [
        "wild Mustang horses running across open desert or western range",
    ]},
    {"tag": "Quarter Horse", "domain": "equine", "parent": "Horse", "hierarchy": "Subjects|Animals|Horses|Quarter_Horse", "min_cos": 0.245, "prompts": [
        "American Quarter Horse working ranch horse in pasture or corral",
    ]},
    {"tag": "Arabian Horse", "domain": "equine", "parent": "Horse", "hierarchy": "Subjects|Animals|Horses|Arabian_Horse", "min_cos": 0.250, "prompts": [
        "an Arabian horse with dished face profile and high arched tail",
    ]},
    {"tag": "Thoroughbred", "domain": "equine", "parent": "Horse", "hierarchy": "Subjects|Animals|Horses|Thoroughbred", "min_cos": 0.250, "prompts": [
        "a tall athletic Thoroughbred horse",
    ]},
    {"tag": "Clydesdale / Draft Horse", "domain": "equine", "parent": "Horse", "hierarchy": "Subjects|Animals|Horses|Draft_Horse", "min_cos": 0.250, "prompts": [
        "a heavy Clydesdale, Percheron, or Belgian draft horse with feathered hooves",
    ]},
    {"tag": "Appaloosa", "domain": "equine", "parent": "Horse", "hierarchy": "Subjects|Animals|Horses|Appaloosa", "min_cos": 0.250, "prompts": [
        "a spotted Appaloosa horse with leopard blanket coat pattern",
    ]},
    {"tag": "Paint / Pinto Horse", "domain": "equine", "parent": "Horse", "hierarchy": "Subjects|Animals|Horses|Paint_Horse", "min_cos": 0.245, "prompts": [
        "a two-tone American Paint or Pinto horse with white and brown patches",
    ]},
    {"tag": "Palomino", "domain": "equine", "parent": "Horse", "hierarchy": "Subjects|Animals|Horses|Palomino", "min_cos": 0.245, "prompts": [
        "a golden yellow Palomino horse with white silver mane and tail",
    ]},
    {"tag": "Foal", "domain": "equine", "parent": "Horse", "hierarchy": "Subjects|Animals|Horses|Foal", "min_cos": 0.250, "prompts": [
        "a young foal or colt standing beside a mare horse",
    ]},
    {"tag": "Pony", "domain": "equine", "parent": "Horse", "hierarchy": "Subjects|Animals|Horses|Pony", "min_cos": 0.250, "prompts": [
        "a small stocky pony with thick mane",
    ]},

    # 4. Ornithology, Wildlife & Flora
    {"tag": "Great Blue Heron", "domain": "ornithology_wildlife", "parent": "Bird", "hierarchy": "Subjects|Animals|Birds|Great_Blue_Heron", "min_cos": 0.245, "prompts": [
        "a tall Great Blue Heron wading bird with long legs and dagger bill",
    ]},
    {"tag": "Snowy Egret", "domain": "ornithology_wildlife", "parent": "Bird", "hierarchy": "Subjects|Animals|Birds|Snowy_Egret", "min_cos": 0.245, "prompts": [
        "a white Snowy Egret or Great Egret wading bird in shallow water",
    ]},
    {"tag": "Brown Pelican", "domain": "ornithology_wildlife", "parent": "Bird", "hierarchy": "Subjects|Animals|Birds|Brown_Pelican", "min_cos": 0.245, "prompts": [
        "a Brown Pelican or White Pelican seabird with large throat pouch flying over ocean",
    ]},
    {"tag": "Sandhill Crane", "domain": "ornithology_wildlife", "parent": "Bird", "hierarchy": "Subjects|Animals|Birds|Sandhill_Crane", "min_cos": 0.245, "prompts": [
        "tall grey Sandhill Cranes with red crown in wetland marsh or field",
    ]},
    {"tag": "Avocet", "domain": "ornithology_wildlife", "parent": "Bird", "hierarchy": "Subjects|Animals|Birds|Avocet", "min_cos": 0.250, "prompts": [
        "an American Avocet or shorebird with upturned bill wading in shallow water",
    ]},
    {"tag": "Cormorant", "domain": "ornithology_wildlife", "parent": "Bird", "hierarchy": "Subjects|Animals|Birds|Cormorant", "min_cos": 0.250, "prompts": [
        "a dark Cormorant seabird perched on coastal rocks or pilings drying its wings",
    ]},
    {"tag": "Seagull", "domain": "ornithology_wildlife", "parent": "Bird", "hierarchy": "Subjects|Animals|Birds|Gull", "min_cos": 0.245, "prompts": [
        "a white and grey seagull or coastal gull flying over beach or pier",
    ]},
    {"tag": "Bald Eagle", "domain": "ornithology_wildlife", "parent": "Bird", "hierarchy": "Subjects|Animals|Birds|Bald_Eagle", "min_cos": 0.250, "prompts": [
        "a Bald Eagle raptor with white head and yellow beak",
    ]},
    {"tag": "Red-Tailed Hawk", "domain": "ornithology_wildlife", "parent": "Bird", "hierarchy": "Subjects|Animals|Birds|Red_Tailed_Hawk", "min_cos": 0.250, "prompts": [
        "a Red-Tailed Hawk or Buteo raptor perched or soaring",
    ]},
    {"tag": "Osprey", "domain": "ornithology_wildlife", "parent": "Bird", "hierarchy": "Subjects|Animals|Birds|Osprey", "min_cos": 0.250, "prompts": [
        "an Osprey sea hawk diving or perched near water",
    ]},
    {"tag": "Great Horned Owl", "domain": "ornithology_wildlife", "parent": "Bird", "hierarchy": "Subjects|Animals|Birds|Great_Horned_Owl", "min_cos": 0.250, "prompts": [
        "a Great Horned Owl or nocturnal owl with ear tufts and yellow eyes",
    ]},
    {"tag": "Hummingbird", "domain": "ornithology_wildlife", "parent": "Bird", "hierarchy": "Subjects|Animals|Birds|Hummingbird", "min_cos": 0.255, "prompts": [
        "a tiny iridescent hummingbird hovering near flowers",
    ]},
    {"tag": "Mallard", "domain": "ornithology_wildlife", "parent": "Bird", "hierarchy": "Subjects|Animals|Birds|Mallard", "min_cos": 0.250, "prompts": [
        "a Mallard duck with iridescent green head swimming on water",
    ]},
    {"tag": "Canada Goose", "domain": "ornithology_wildlife", "parent": "Bird", "hierarchy": "Subjects|Animals|Birds|Canada_Goose", "min_cos": 0.250, "prompts": [
        "a Canada Goose with black neck and white chinstrap",
    ]},
    {"tag": "Bison", "domain": "ornithology_wildlife", "parent": "Bison", "hierarchy": "Subjects|Animals|Wildlife|Bison", "min_cos": 0.245, "prompts": [
        "shaggy brown American Bison or buffalo grazing on prairie or snow",
    ]},
    {"tag": "Elk", "domain": "ornithology_wildlife", "parent": "Wildlife", "hierarchy": "Subjects|Animals|Wildlife|Elk", "min_cos": 0.250, "prompts": [
        "a rocky mountain Elk bull or herd with large antlers",
    ]},
    {"tag": "Mule Deer", "domain": "ornithology_wildlife", "parent": "Wildlife", "hierarchy": "Subjects|Animals|Wildlife|Deer", "min_cos": 0.250, "prompts": [
        "a Mule Deer or white-tailed deer with large ears in nature",
    ]},
    {"tag": "Moose", "domain": "ornithology_wildlife", "parent": "Wildlife", "hierarchy": "Subjects|Animals|Wildlife|Moose", "min_cos": 0.255, "prompts": [
        "a large Moose with broad palmate antlers in willow marsh or forest",
    ]},
    {"tag": "Bighorn Sheep", "domain": "ornithology_wildlife", "parent": "Wildlife", "hierarchy": "Subjects|Animals|Wildlife|Bighorn_Sheep", "min_cos": 0.255, "prompts": [
        "a Rocky Mountain or Desert Bighorn Sheep ram with curved horns on cliff",
    ]},
    {"tag": "Grizzly / Black Bear", "domain": "ornithology_wildlife", "parent": "Wildlife", "hierarchy": "Subjects|Animals|Wildlife|Bear", "min_cos": 0.255, "prompts": [
        "a live wild Grizzly Bear or Black Bear in forest or mountain meadow",
    ]},
    {"tag": "Coyote", "domain": "ornithology_wildlife", "parent": "Wildlife", "hierarchy": "Subjects|Animals|Wildlife|Coyote", "min_cos": 0.255, "prompts": [
        "a wild Coyote walking through sagebrush, desert, or snowy field",
    ]},
    {"tag": "Red Fox", "domain": "ornithology_wildlife", "parent": "Wildlife", "hierarchy": "Subjects|Animals|Wildlife|Red_Fox", "min_cos": 0.255, "prompts": [
        "a wild Red Fox with orange fur and bushy white-tipped tail",
    ]},
    {"tag": "Sea Otter", "domain": "ornithology_wildlife", "parent": "Wildlife", "hierarchy": "Subjects|Animals|Marine|Sea_Otter", "min_cos": 0.255, "prompts": [
        "a floating Sea Otter in Pacific kelp forest water",
    ]},
    {"tag": "Seal / Sea Lion", "domain": "ornithology_wildlife", "parent": "Wildlife", "hierarchy": "Subjects|Animals|Marine|Seal_Sea_Lion", "min_cos": 0.250, "prompts": [
        "harbor seals or California sea lions hauled out on coastal rocks or beach",
    ]},
    {"tag": "Humpback Whale", "domain": "ornithology_wildlife", "parent": "Wildlife", "hierarchy": "Subjects|Animals|Marine|Humpback_Whale", "min_cos": 0.255, "prompts": [
        "a Humpback Whale or gray whale tail fluke or breaching in ocean water",
    ]},
    {"tag": "Coast Redwood", "domain": "flora_trees", "parent": "Trees", "hierarchy": "Subjects|Flora|Trees|Coast_Redwood", "min_cos": 0.245, "prompts": [
        "towering Coast Redwood tree trunks in misty Pacific Northwest forest",
    ]},
    {"tag": "Giant Sequoia", "domain": "flora_trees", "parent": "Trees", "hierarchy": "Subjects|Flora|Trees|Giant_Sequoia", "min_cos": 0.250, "prompts": [
        "massive cinnamon-red Giant Sequoia tree trunk in Sierra Nevada grove",
    ]},
    {"tag": "Quaking Aspen", "domain": "flora_trees", "parent": "Trees", "hierarchy": "Subjects|Flora|Trees|Quaking_Aspen", "min_cos": 0.245, "prompts": [
        "white-barked Quaking Aspen trees with golden yellow autumn leaves",
    ]},
    {"tag": "Monterey Cypress", "domain": "flora_trees", "parent": "Trees", "hierarchy": "Subjects|Flora|Trees|Monterey_Cypress", "min_cos": 0.245, "prompts": [
        "windswept gnarled Monterey Cypress tree on rocky California coastline or bayou cypress swamp",
    ]},
    {"tag": "Joshua Tree", "domain": "flora_trees", "parent": "Trees", "hierarchy": "Subjects|Flora|Trees|Joshua_Tree", "min_cos": 0.245, "prompts": [
        "spiky branching Joshua Tree yucca brevifolia in Mojave Desert",
    ]},
    {"tag": "Ponderosa Pine", "domain": "flora_trees", "parent": "Trees", "hierarchy": "Subjects|Flora|Trees|Ponderosa_Pine", "min_cos": 0.245, "prompts": [
        "tall Ponderosa Pine or alpine conifer evergreen forest trees",
    ]},
    {"tag": "Oak", "domain": "flora_trees", "parent": "Trees", "hierarchy": "Subjects|Flora|Trees|Oak", "min_cos": 0.245, "prompts": [
        "spreading California live oak or valley oak tree with gnarly branches",
    ]},
    {"tag": "Palm", "domain": "flora_trees", "parent": "Trees", "hierarchy": "Subjects|Flora|Trees|Palm", "min_cos": 0.245, "prompts": [
        "tall tropical fan palm trees or desert palm oasis",
    ]},
    {"tag": "Orchard Blossoms", "domain": "flora_trees", "parent": "Trees", "hierarchy": "Subjects|Flora|Trees|Orchard_Blossoms", "min_cos": 0.245, "prompts": [
        "blooming white and pink fruit orchard trees in spring blossom rows",
    ]},
    {"tag": "Saguaro Cactus", "domain": "flora_trees", "parent": "Cactus", "hierarchy": "Subjects|Flora|Desert_Plants|Saguaro_Cactus", "min_cos": 0.245, "prompts": [
        "tall columnar Saguaro cactus with arms in Sonoran desert",
    ]},
    {"tag": "California Poppies", "domain": "flora_trees", "parent": "Wildflowers", "hierarchy": "Subjects|Flora|Wildflowers|California_Poppies", "min_cos": 0.245, "prompts": [
        "vibrant orange California poppies blooming on hillside",
    ]},
    {"tag": "Lupine", "domain": "flora_trees", "parent": "Wildflowers", "hierarchy": "Subjects|Flora|Wildflowers|Lupine", "min_cos": 0.245, "prompts": [
        "purple and blue lupine wildflowers blooming in meadow",
    ]},
    {"tag": "Wildflowers", "domain": "flora_trees", "parent": "Wildflowers", "hierarchy": "Subjects|Flora|Wildflowers", "min_cos": 0.240, "prompts": [
        "field of colorful blooming wildflowers in meadow or desert",
    ]},
    {"tag": "Monstera", "domain": "indoor_flora", "parent": "Plants", "hierarchy": "Subjects|Flora|Houseplants|Monstera", "min_cos": 0.245, "prompts": [
        "a tropical Monstera deliciosa houseplant with split fenestrated green leaves",
    ]},
    {"tag": "Pothos", "domain": "indoor_flora", "parent": "Plants", "hierarchy": "Subjects|Flora|Houseplants|Pothos", "min_cos": 0.245, "prompts": [
        "trailing green and variegated Pothos ivy vine houseplant in pot",
    ]},
    {"tag": "Fiddle Leaf Fig", "domain": "indoor_flora", "parent": "Plants", "hierarchy": "Subjects|Flora|Houseplants|Fiddle_Leaf_Fig", "min_cos": 0.245, "prompts": [
        "an indoor Fiddle Leaf Fig tree houseplant with large violin-shaped leaves",
    ]},
    {"tag": "Succulent", "domain": "indoor_flora", "parent": "Plants", "hierarchy": "Subjects|Flora|Houseplants|Succulent", "min_cos": 0.245, "prompts": [
        "fleshy rosette succulent plant, aloe, or echeveria in planter",
    ]},
    {"tag": "Morel / Mushroom", "domain": "flora_trees", "parent": "Plants", "hierarchy": "Subjects|Flora|Fungi|Morel_Mushroom", "min_cos": 0.255, "prompts": [
        "wild morel mushroom or forest fungi fruiting body on woodland floor",
    ]},

    # 5. Aerial Agriculture & Civil Infrastructure
    {"tag": "Center-Pivot Irrigation", "domain": "aerial_agriculture", "parent": "Farmland", "hierarchy": "Landscape|Agriculture|Center_Pivot_Irrigation", "min_cos": 0.240, "prompts": [
        "aerial view of circular center-pivot irrigation crop fields and wheeled sprinkler arm",
    ]},
    {"tag": "Circular Crop Field", "domain": "aerial_agriculture", "parent": "Farmland", "hierarchy": "Landscape|Agriculture|Circular_Crop_Field", "min_cos": 0.240, "prompts": [
        "overhead aerial geometry of green and gold circular agricultural crop circles in desert farmland",
    ]},
    {"tag": "Apricot / Stone Fruit Orchard", "domain": "aerial_agriculture", "parent": "Farmland", "hierarchy": "Landscape|Agriculture|Stone_Fruit_Orchard", "min_cos": 0.245, "prompts": [
        "aerial or eye-level view of apricot, peach, or cherry stone fruit orchard tree rows",
    ]},
    {"tag": "Almond Orchard", "domain": "aerial_agriculture", "parent": "Farmland", "hierarchy": "Landscape|Agriculture|Almond_Orchard", "min_cos": 0.245, "prompts": [
        "geometric grid rows of California almond orchard trees",
    ]},
    {"tag": "Vineyard Rows", "domain": "aerial_agriculture", "parent": "Farmland", "hierarchy": "Landscape|Agriculture|Vineyard_Rows", "min_cos": 0.245, "prompts": [
        "parallel trellised grapevine vineyard rows across rolling hills",
    ]},
    {"tag": "Citrus Grove", "domain": "aerial_agriculture", "parent": "Farmland", "hierarchy": "Landscape|Agriculture|Citrus_Grove", "min_cos": 0.245, "prompts": [
        "dense dark green round citrus orange or lemon grove orchard trees",
    ]},
    {"tag": "Wheat / Grain Field", "domain": "aerial_agriculture", "parent": "Farmland", "hierarchy": "Landscape|Agriculture|Wheat_Grain_Field", "min_cos": 0.240, "prompts": [
        "golden wheat fields, harvested grain stubble, or rippling cereal crops",
    ]},
    {"tag": "Green Farmland", "domain": "aerial_agriculture", "parent": "Farmland", "hierarchy": "Landscape|Agriculture|Green_Farmland", "min_cos": 0.240, "prompts": [
        "lush emerald green cultivated farmland pastures and agricultural fields",
    ]},
    {"tag": "Ploughed / Fallow Field", "domain": "aerial_agriculture", "parent": "Farmland", "hierarchy": "Landscape|Agriculture|Ploughed_Fallow_Field", "min_cos": 0.240, "prompts": [
        "dark ploughed soil furrows and tilled fallow agricultural earth",
    ]},
    {"tag": "Contour Farming", "domain": "aerial_agriculture", "parent": "Farmland", "hierarchy": "Landscape|Agriculture|Contour_Farming", "min_cos": 0.240, "prompts": [
        "sweeping curved contour farming strips and terraced Palouse agricultural hills",
    ]},
    {"tag": "Irrigation Canal", "domain": "aerial_agriculture", "parent": "Farmland", "hierarchy": "Landscape|Agriculture|Irrigation_Canal", "min_cos": 0.245, "prompts": [
        "concrete-lined agricultural aqueduct or irrigation canal channel cutting through farmland",
    ]},
    {"tag": "Grain Silo", "domain": "aerial_agriculture", "parent": "Barn", "hierarchy": "Architecture|Ranch|Grain_Silo", "min_cos": 0.245, "prompts": [
        "cylindrical metal or concrete grain silos and tall rural grain elevator towers",
    ]},
    {"tag": "Tractor / Combine", "domain": "aerial_agriculture", "parent": "Farmland", "hierarchy": "Subjects|Agriculture|Tractor_Combine", "min_cos": 0.250, "prompts": [
        "agricultural farm tractor or combine harvester working in a field",
    ]},
    {"tag": "Highway Overpass", "domain": "civil_infrastructure", "parent": "Bridge", "hierarchy": "Architecture|Infrastructure|Highway_Overpass", "min_cos": 0.240, "prompts": [
        "elevated concrete highway overpass, freeway ramp, or road bridge span",
    ]},
    {"tag": "Cloverleaf Interchange", "domain": "civil_infrastructure", "parent": "Bridge", "hierarchy": "Architecture|Infrastructure|Cloverleaf_Interchange", "min_cos": 0.245, "prompts": [
        "aerial view of curving multi-level freeway cloverleaf interchange ramps",
    ]},
    {"tag": "Suspension Bridge", "domain": "civil_infrastructure", "parent": "Bridge", "hierarchy": "Architecture|Infrastructure|Suspension_Bridge", "min_cos": 0.245, "prompts": [
        "a tall suspension bridge or cable-stayed bridge with towers and steel cables over water",
    ]},
    {"tag": "Steel Truss Bridge", "domain": "civil_infrastructure", "parent": "Bridge", "hierarchy": "Architecture|Infrastructure|Steel_Truss_Bridge", "min_cos": 0.245, "prompts": [
        "an industrial steel truss bridge or arch bridge with riveted metal girders",
    ]},
    {"tag": "Viaduct", "domain": "civil_infrastructure", "parent": "Bridge", "hierarchy": "Architecture|Infrastructure|Viaduct", "min_cos": 0.245, "prompts": [
        "a long multi-arch concrete or stone viaduct bridge spanning a valley or urban rail corridor",
    ]},
    {"tag": "Skyscraper", "domain": "civil_infrastructure", "parent": "Building", "hierarchy": "Architecture|Urban|Skyscraper", "min_cos": 0.240, "prompts": [
        "tall modern downtown skyscrapers and high-rise commercial office towers",
    ]},
    {"tag": "Glass Curtain Wall", "domain": "civil_infrastructure", "parent": "Building", "hierarchy": "Architecture|Urban|Glass_Curtain_Wall", "min_cos": 0.245, "prompts": [
        "geometric reflective glass curtain wall facade of a modern skyscraper",
    ]},
    {"tag": "Construction Scaffolding", "domain": "civil_infrastructure", "parent": "Building", "hierarchy": "Architecture|Urban|Construction_Scaffolding", "min_cos": 0.250, "prompts": [
        "metal construction scaffolding, tower crane, or building structural framework",
    ]},
    {"tag": "Amusement Pier", "domain": "civil_infrastructure", "parent": "Pier", "hierarchy": "Architecture|Coastal|Amusement_Pier", "min_cos": 0.245, "prompts": [
        "coastal ocean amusement pier boardwalk with carnival rides over the surf",
    ]},
    {"tag": "Ferris Wheel", "domain": "civil_infrastructure", "parent": "Pier", "hierarchy": "Architecture|Coastal|Ferris_Wheel", "min_cos": 0.250, "prompts": [
        "an illuminated Ferris wheel on a pier or carnival midway",
    ]},
    {"tag": "Roller Coaster", "domain": "civil_infrastructure", "parent": "Pier", "hierarchy": "Architecture|Coastal|Roller_Coaster", "min_cos": 0.250, "prompts": [
        "looping steel or wooden roller coaster tracks at an amusement park or pier",
    ]},
    {"tag": "Shipping Port / Cranes", "domain": "civil_infrastructure", "parent": "Industrial", "hierarchy": "Architecture|Industrial|Shipping_Port_Cranes", "min_cos": 0.250, "prompts": [
        "industrial seaport container terminal with gantry cranes and cargo ships",
    ]},
    {"tag": "Oil Derrick / Pumpjack", "domain": "civil_infrastructure", "parent": "Oil Fields", "hierarchy": "Architecture|Industrial|Oil_Derrick_Pumpjack", "min_cos": 0.245, "prompts": [
        "nodding donkey oil field pumpjacks, oil derricks, and steam pipelines",
    ]},
    {"tag": "Refinery", "domain": "civil_infrastructure", "parent": "Oil Facility", "hierarchy": "Architecture|Industrial|Refinery", "min_cos": 0.245, "prompts": [
        "industrial petrochemical oil refinery distillation towers, pipes, and storage tanks",
    ]},
    {"tag": "Solar Farm", "domain": "civil_infrastructure", "parent": "Industrial", "hierarchy": "Architecture|Industrial|Solar_Farm", "min_cos": 0.250, "prompts": [
        "arrays of photovoltaic solar panels in a desert solar energy farm",
    ]},
    {"tag": "Wind Turbine", "domain": "civil_infrastructure", "parent": "Industrial", "hierarchy": "Architecture|Industrial|Wind_Turbine", "min_cos": 0.250, "prompts": [
        "tall white wind turbines with three blades on ridge or wind farm",
    ]},

    # 6. Science, Macro, Optical, Product & Interior Decor
    {"tag": "Ferrofluid", "domain": "science_macro_optical", "parent": "Macro Photography", "hierarchy": "Subjects|Science_And_Macro|Ferrofluid", "min_cos": 0.250, "prompts": [
        "glossy black magnetic ferrofluid liquid forming sharp conical spikes in a magnetic field",
    ]},
    {"tag": "Magnetic Spikes / Magnetism", "domain": "science_macro_optical", "parent": "Macro Photography", "hierarchy": "Subjects|Science_And_Macro|Magnetic_Spikes", "min_cos": 0.250, "prompts": [
        "macro close-up of magnetic field spikes, iron filings, or ferrofluid rosettes under colored studio lighting",
    ]},
    {"tag": "Macro Photography", "domain": "science_macro_optical", "parent": "Macro Photography", "hierarchy": "Subjects|Science_And_Macro|Macro_Photography", "min_cos": 0.245, "prompts": [
        "extreme close-up macro photography showing fine microscopic surface texture and shallow depth of field",
    ]},
    {"tag": "Bee / Honeybee", "domain": "science_macro_optical", "parent": "Macro Photography", "mids": ["Insect", "Bee", "Macro Photography"], "hierarchy": "Subjects|Wildlife_And_Insects|Bee", "min_cos": 0.220, "prompts": [
        "extreme macro photograph of a honeybee, bumblebee, or bee head, compound eyes, antennae, and thorax fur",
        "macro focus stacked image of a bee up close showing microscopic hair and eye facets",
        "close-up macro photography of a bee on a studio background or flower",
    ]},
    {"tag": "Insect / Macro", "domain": "science_macro_optical", "parent": "Macro Photography", "mids": ["Insect", "Macro Photography"], "hierarchy": "Subjects|Wildlife_And_Insects|Insect", "min_cos": 0.220, "prompts": [
        "extreme macro photograph of an insect, bug, beetle, or arthropod up close",
        "scientific focus-stacked macro image of an insect head and compound eyes",
    ]},
    {"tag": "Focus Stacked Macro", "domain": "science_macro_optical", "parent": "Macro Photography", "mids": ["Macro Photography", "Focus Stacking"], "hierarchy": "Subjects|Science_And_Macro|Focus_Stacked", "min_cos": 0.230, "prompts": [
        "extreme depth of field focus stacked macro photograph of microscopic subjects, insect head, or crystalline facets",
    ]},
    {"tag": "Photomicrography / Microscopic", "domain": "science_macro_optical", "parent": "Macro Photography", "hierarchy": "Subjects|Science_And_Macro|Photomicrography", "min_cos": 0.255, "prompts": [
        "scientific photomicrography through a microscope showing crystals, cells, or polarized light structures",
    ]},
    {"tag": "Light Refraction", "domain": "science_macro_optical", "parent": "Macro Photography", "hierarchy": "Subjects|Science_And_Macro|Light_Refraction", "min_cos": 0.245, "prompts": [
        "optical light refraction bending beams through glass, lens, water, or crystal",
    ]},
    {"tag": "Optical Prism / Dispersion", "domain": "science_macro_optical", "parent": "Macro Photography", "hierarchy": "Subjects|Science_And_Macro|Optical_Prism", "min_cos": 0.250, "prompts": [
        "glass optical prism splitting light into rainbow spectral dispersion",
    ]},
    {"tag": "Caustics", "domain": "science_macro_optical", "parent": "Macro Photography", "hierarchy": "Subjects|Science_And_Macro|Caustics", "min_cos": 0.250, "prompts": [
        "shimmering optical caustics light patterns refracted through glass or rippling water",
    ]},
    {"tag": "Diffusion Filter / Halation", "domain": "science_macro_optical", "parent": "Macro Photography", "hierarchy": "Subjects|Science_And_Macro|Diffusion_Filter", "min_cos": 0.250, "prompts": [
        "glowing halation bloom and soft optical mist diffusion around bright light sources",
    ]},
    {"tag": "Water Droplet / Splash", "domain": "science_macro_optical", "parent": "Macro Photography", "hierarchy": "Subjects|Science_And_Macro|Water_Droplet", "min_cos": 0.250, "prompts": [
        "high-speed macro photograph of liquid water droplets, crown splash, or dew drops",
    ]},
    {"tag": "Oil and Water Abstract", "domain": "science_macro_optical", "parent": "Macro Photography", "hierarchy": "Subjects|Science_And_Macro|Oil_And_Water", "min_cos": 0.250, "prompts": [
        "colorful macro abstract of floating oil bubbles on water surface",
    ]},
    {"tag": "Stop Motion Set", "domain": "studio_product", "parent": "Still Life", "hierarchy": "Subjects|Studio_And_Product|Stop_Motion_Set", "min_cos": 0.255, "prompts": [
        "a miniature tabletop stop motion animation set with armatures, props, and studio rigs",
    ]},
    {"tag": "Scanography / Scanner Art", "domain": "studio_product", "parent": "Still Life", "hierarchy": "Subjects|Studio_And_Product|Scanography", "min_cos": 0.255, "prompts": [
        "flatbed scanner scanography art of botanical objects or glass against pitch black background",
    ]},
    {"tag": "Whiskey / Bourbon Bottle", "domain": "studio_product", "parent": "Still Life", "hierarchy": "Subjects|Studio_And_Product|Whiskey_Bourbon_Bottle", "min_cos": 0.250, "prompts": [
        "studio product photograph of an amber whiskey, bourbon, or scotch glass bottle with label",
    ]},
    {"tag": "Spirits Decanter", "domain": "studio_product", "parent": "Still Life", "hierarchy": "Subjects|Studio_And_Product|Spirits_Decanter", "min_cos": 0.250, "prompts": [
        "a cut crystal or glass spirits liquor decanter with stopper",
    ]},
    {"tag": "Rocks Glass / Tumbler", "domain": "studio_product", "parent": "Still Life", "hierarchy": "Subjects|Studio_And_Product|Rocks_Glass_Tumbler", "min_cos": 0.250, "prompts": [
        "a crystal rocks glass or whiskey tumbler with ice cube and amber cocktail",
    ]},
    {"tag": "Cosmetic Lotion Bottle", "domain": "studio_product", "parent": "Still Life", "hierarchy": "Subjects|Studio_And_Product|Cosmetic_Lotion_Bottle", "min_cos": 0.250, "prompts": [
        "commercial skincare cosmetic lotion pump bottle or cream jar",
    ]},
    {"tag": "Dropper / Serum Bottle", "domain": "studio_product", "parent": "Still Life", "hierarchy": "Subjects|Studio_And_Product|Dropper_Serum_Bottle", "min_cos": 0.250, "prompts": [
        "a small glass cosmetic serum bottle with pipette dropper",
    ]},
    {"tag": "Perfume Flacon", "domain": "studio_product", "parent": "Still Life", "hierarchy": "Subjects|Studio_And_Product|Perfume_Flacon", "min_cos": 0.250, "prompts": [
        "an elegant glass perfume bottle flacon with atomizer spray",
    ]},
    {"tag": "Luxury Watch", "domain": "studio_product", "parent": "Still Life", "hierarchy": "Subjects|Studio_And_Product|Luxury_Watch", "min_cos": 0.255, "prompts": [
        "macro studio shot of a mechanical luxury wristwatch dial, bezel, and chronograph hands",
    ]},
    {"tag": "Glass Sculpture / Crystal", "domain": "science_macro_optical", "parent": "Macro Photography", "mids": ["Light Refraction", "Crystal", "Glass Art"], "hierarchy": "Subjects|Science_And_Macro|Glass_Sculpture", "min_cos": 0.238, "prompts": [
        "studio macro photograph of a translucent blue and white art glass sculpture or crystal figurine glowing against a pitch black background with reflection",
        "close-up of blown glass art, crystal sculpture, or translucent glass object with light refraction on a dark reflective surface",
    ]},
    {"tag": "Studio Black Backdrop", "domain": "studio_product", "parent": "Still Life", "hierarchy": "Subjects|Studio_And_Product|Studio_Black_Backdrop", "min_cos": 0.238, "prompts": [
        "studio still-life subject isolated against a pitch black background with dramatic rim lighting and dark mirror reflection",
    ]},
    {"tag": "Wine Bottle", "domain": "studio_product", "parent": "Still Life", "mids": ["Wine"], "hierarchy": "Subjects|Culinary_And_Wine|Wine_Bottle", "min_cos": 0.224, "prompts": [
        "glass wine bottles with vineyard labels standing on a wooden wine barrel or table at a winery tasting",
        "close-up of red or white wine bottles with labels and foil capsules",
        "a person holding a wine bottle next to wine glasses on a wooden barrel",
    ]},
    {"tag": "Wine Glass", "domain": "studio_product", "parent": "Still Life", "mids": ["Wine", "Glassware"], "hierarchy": "Subjects|Culinary_And_Wine|Wine_Glass", "min_cos": 0.235, "prompts": [
        "stemmed crystal wine glasses or goblets on a wooden barrel or table at a wine tasting",
        "clear stemmed wine glass next to wine bottles at a winery",
    ]},
    {"tag": "Wine Barrel", "domain": "studio_product", "parent": "Still Life", "mids": ["Winery"], "hierarchy": "Subjects|Culinary_And_Wine|Wine_Barrel", "min_cos": 0.222, "prompts": [
        "rustic oak wine barrel with metal hoops used as a tasting table at a winery or cellar",
        "wooden oak wine barrel tabletop with wine bottles and stemmed wine glasses",
        "wine bottles with labels and wine glasses sitting on top of a wooden wine barrel",
    ]},
    {"tag": "Wine Tasting / Winery", "domain": "studio_product", "parent": "Still Life", "mids": ["Wine", "Winery"], "hierarchy": "Subjects|Culinary_And_Wine|Wine_Tasting", "min_cos": 0.230, "prompts": [
        "winery tasting event with wine bottles, wine glasses on an oak barrel, and guests holding wine",
        "a person holding a wine bottle next to wine glasses on a wooden barrel at a winery",
    ]},
    {"tag": "Cocktail / Beverage", "domain": "studio_product", "parent": "Still Life", "hierarchy": "Subjects|Culinary_And_Wine|Cocktail_Beverage", "min_cos": 0.245, "prompts": [
        "a cocktail glass, craft beer pint, or beverage glass on a bar counter or restaurant table",
    ]},
    {"tag": "Culinary / Dining", "domain": "studio_product", "parent": "Still Life", "hierarchy": "Subjects|Culinary_And_Wine|Culinary_Dining", "min_cos": 0.245, "prompts": [
        "plated gourmet food dish, charcuterie board, or restaurant dining table meal",
    ]},
    {"tag": "Floral / Purple Dress", "domain": "closet_storage_wellness", "parent": "People", "mids": ["Woman", "Necklace / Jewelry"], "hierarchy": "Subjects|People|Apparel|Dress", "min_cos": 0.222, "prompts": [
        "a woman wearing a purple or floral patterned sleeveless dress and necklace at an event or winery",
        "close-up of a woman in a purple patterned dress holding a wine bottle at a wine tasting",
        "wine tasting table with wine bottles, wine glasses, wooden barrel, and a woman in a purple dress",
    ]},
    {"tag": "Necklace / Jewelry", "domain": "closet_storage_wellness", "parent": "People", "hierarchy": "Subjects|People|Apparel|Jewelry", "min_cos": 0.232, "prompts": [
        "a woman wearing a pendant necklace or jewelry around her neck",
        "a gold chain pendant necklace on a woman's neckline in a purple dress",
    ]},
    {"tag": "Bohemian Tapestry / Woven Throw", "domain": "indoor_decor_textiles", "parent": "Living Room", "hierarchy": "Architecture|Interiors|Bohemian_Tapestry_Throw", "min_cos": 0.232, "prompts": [
        "a patterned bohemian tapestry throw blanket or woven fringed textile draped over a living room couch or bed",
        "a decorative woven geometric throw blanket on an indoor sofa",
    ]},
    {"tag": "Modern / Pop Wall Art", "domain": "indoor_decor_textiles", "parent": "Framed Art", "hierarchy": "Architecture|Interiors|Modern_Pop_Wall_Art", "min_cos": 0.235, "prompts": [
        "modern graphic pop art print, colorful contemporary illustration, or poster hanging on an interior wall",
    ]},
    {"tag": "Framed Art", "domain": "indoor_decor_textiles", "parent": "Framed Art", "hierarchy": "Architecture|Interiors|Framed_Art", "min_cos": 0.230, "prompts": [
        "framed artwork, picture frames, or matted photographs hanging on an indoor room wall",
    ]},
    {"tag": "Decorative Lamp", "domain": "indoor_decor_textiles", "parent": "Living Room", "hierarchy": "Architecture|Interiors|Decorative_Lamp", "min_cos": 0.238, "prompts": [
        "an indoor table lamp, floor lamp, or decorative lampshade in a living room or bedroom",
    ]},
    {"tag": "Couch", "domain": "indoor_decor_textiles", "parent": "Living Room", "hierarchy": "Architecture|Interiors|Couch", "min_cos": 0.230, "prompts": [
        "an upholstered living room couch, sofa, or sectional with throw pillows",
    ]},
    {"tag": "Area Rug / Carpet", "domain": "indoor_decor_textiles", "parent": "Living Room", "hierarchy": "Architecture|Interiors|Area_Rug_Carpet", "min_cos": 0.230, "prompts": [
        "an indoor area rug, plush carpet floor, or woven floor covering in a home",
    ]},

    # 7. Closet, Drawer & Personal / Intimate Wellness
    {"tag": "Sneakers", "domain": "closet_storage_wellness", "parent": "Indoor", "hierarchy": "Subjects|Personal_And_Apparel|Sneakers", "min_cos": 0.245, "prompts": [
        "athletic sneakers, running shoes, or trainers on a floor or closet rack",
    ]},
    {"tag": "Boots", "domain": "closet_storage_wellness", "parent": "Indoor", "hierarchy": "Subjects|Personal_And_Apparel|Boots", "min_cos": 0.245, "prompts": [
        "leather boots, cowboy boots, or ankle boots in a closet or room",
    ]},
    {"tag": "Dresser Drawer", "domain": "closet_storage_wellness", "parent": "Indoor", "hierarchy": "Architecture|Interiors|Dresser_Drawer", "min_cos": 0.245, "prompts": [
        "an open wooden or bedroom dresser drawer storing personal items or clothing",
    ]},
    {"tag": "Wardrobe", "domain": "closet_storage_wellness", "parent": "Indoor", "hierarchy": "Architecture|Interiors|Wardrobe", "min_cos": 0.245, "prompts": [
        "an indoor clothes closet, wardrobe rack, or closet shelves with hangers",
    ]},
    {"tag": "Adult Novelty", "domain": "closet_storage_wellness", "parent": "Indoor", "hierarchy": "Subjects|Personal_Wellness|Adult_Novelty", "min_cos": 0.255, "prompts": [
        "personal intimate wellness adult novelty items stored in a closet or drawer",
    ]},
    {"tag": "Vibrator", "domain": "closet_storage_wellness", "parent": "Indoor", "hierarchy": "Subjects|Personal_Wellness|Vibrator", "min_cos": 0.255, "prompts": [
        "a handheld personal massager vibrator device",
    ]},
    {"tag": "Silicone Toy", "domain": "closet_storage_wellness", "parent": "Indoor", "hierarchy": "Subjects|Personal_Wellness|Silicone_Toy", "min_cos": 0.255, "prompts": [
        "molded silicone intimate wellness adult toy",
    ]},
]

GLOBAL_LANDMARK_GAZETTEER: Dict[str, Dict[str, Any]] = {
    "iceland_hallgrimskirkja": {
        "probe_key": "lm_hallgrimskirkja",
        "specific_location": "Hallgrímskirkja, Reykjavík",
        "state_region": "Capital Region",
        "country": "Iceland",
        "hierarchy": "Places|Europe|Iceland|Reykjavik|Hallgrimskirkja",
        "tags": ["Iceland", "Reykjavik", "Reykjavík", "Hallgrimskirkja", "Hallgrímskirkja", "Church Tower", "Nordic Architecture", "Europe"],
    },
    "iceland_kirkjufell": {
        "probe_key": "lm_kirkjufell",
        "specific_location": "Kirkjufell Mountain",
        "state_region": "Snæfellsnes",
        "country": "Iceland",
        "hierarchy": "Places|Europe|Iceland|Kirkjufell",
        "tags": ["Iceland", "Kirkjufell", "Kirkjufellsfoss", "Snæfellsnes", "Waterfall", "Mountain Peak", "Nordic Landscape", "Europe"],
    },
    "iceland_jokulsarlon": {
        "probe_key": "lm_jokulsarlon",
        "specific_location": "Jökulsárlón & Diamond Beach",
        "state_region": "Austurland",
        "country": "Iceland",
        "hierarchy": "Places|Europe|Iceland|Jokulsarlon",
        "tags": ["Iceland", "Jokulsarlon", "Jökulsárlón", "Diamond Beach", "Glacial Lagoon", "Icebergs", "Black Sand Beach", "Europe"],
    },
    "iceland_reynisfjara": {
        "probe_key": "lm_reynisfjara",
        "specific_location": "Reynisfjara Black Sand Beach",
        "state_region": "Suðurland",
        "country": "Iceland",
        "hierarchy": "Places|Europe|Iceland|Reynisfjara",
        "tags": ["Iceland", "Reynisfjara", "Reynisdrangar", "Vik", "Black Sand Beach", "Basalt Sea Stacks", "North Atlantic", "Europe"],
    },
    "iceland_gullfoss": {
        "probe_key": "lm_gullfoss",
        "specific_location": "Gullfoss & Icelandic Waterfalls",
        "state_region": "Suðurland",
        "country": "Iceland",
        "hierarchy": "Places|Europe|Iceland|Gullfoss",
        "tags": ["Iceland", "Gullfoss", "Icelandic Waterfall", "Waterfall", "Nordic Landscape", "Europe"],
    },
    "valley_of_the_gods": {
        "probe_key": "lm_valley_of_gods",
        "specific_location": "Valley of the Gods",
        "state_region": "Utah",
        "country": "United States",
        "hierarchy": "Places|United States|Utah|Valley of the Gods",
        "tags": ["Valley of the Gods", "Utah", "Butte", "Buttes", "Sandstone Butte", "Red Rock Spire", "Desert Monolith", "Cedar Mesa"],
    },
    "monument_valley": {
        "probe_key": "lm_monument_valley",
        "specific_location": "Monument Valley",
        "state_region": "Arizona",
        "country": "United States",
        "hierarchy": "Places|United States|Arizona|Monument Valley",
        "tags": ["Monument Valley", "Arizona", "Utah", "Butte", "Buttes", "Mitten Buttes", "Sandstone Butte", "Desert Monolith", "Colorado Plateau"],
    },
    "castleton_fisher": {
        "probe_key": "lm_castleton_fisher",
        "specific_location": "Castleton Tower & Fisher Towers",
        "state_region": "Utah",
        "country": "United States",
        "hierarchy": "Places|United States|Utah|Moab|Castleton Tower",
        "tags": ["Castleton Tower", "Fisher Towers", "Castle Valley", "Moab", "Utah", "Butte", "Buttes", "Sandstone Tower", "Desert Spire"],
    },
    "devils_tower": {
        "probe_key": "lm_devils_tower",
        "specific_location": "Devils Tower",
        "state_region": "Wyoming",
        "country": "United States",
        "hierarchy": "Places|United States|Wyoming|Devils Tower",
        "tags": ["Devils Tower", "Wyoming", "Butte", "Buttes", "Volcanic Monolith"],
    },
    "grand_tetons": {
        "probe_key": "lm_grand_tetons",
        "specific_location": "Grand Teton National Park",
        "state_region": "Wyoming",
        "country": "United States",
        "hierarchy": "Places|United States|Wyoming|Grand Tetons",
        "tags": ["Grand Teton National Park", "Grand Tetons", "Tetons", "Teton Range", "Wyoming", "Mountain Peak", "Alpine Peaks", "Jackson Hole"],
    },
    "mount_rainier": {
        "probe_key": "lm_mount_rainier",
        "specific_location": "Mount Rainier & Cascades",
        "state_region": "Washington",
        "country": "United States",
        "hierarchy": "Places|United States|Washington|Mount Rainier",
        "tags": ["Mount Rainier", "Cascades", "Cascade Range", "Washington", "Glaciated Peak", "Volcanic Peak", "Mountain Peak"],
    },
    "yosemite": {
        "probe_key": "lm_yosemite",
        "specific_location": "Yosemite National Park",
        "state_region": "California",
        "country": "United States",
        "hierarchy": "Places|United States|California|Yosemite",
        "tags": ["Yosemite", "Yosemite National Park", "Half Dome", "El Capitan", "Yosemite Valley", "California", "Granite Monolith", "Sierra Nevada"],
    },
    "mono_lake": {
        "probe_key": "lm_mono_lake",
        "specific_location": "Mono Lake",
        "state_region": "California",
        "country": "United States",
        "hierarchy": "Places|United States|California|Mono Lake",
        "tags": ["Mono Lake", "Tufa Towers", "Eastern Sierra", "Highway 395", "California", "Sierra Nevada"],
    },
    "washington_monument": {
        "probe_key": "lm_washington_monument",
        "specific_location": "Washington Monument",
        "state_region": "Washington DC",
        "country": "United States",
        "hierarchy": "Places|United States|Washington DC|Washington Monument",
        "tags": ["Washington Monument", "Washington DC", "District of Columbia", "National Mall", "Obelisk", "Monument", "American Flags", "Circle of Flags"],
    },
    "chicago_skyline": {
        "probe_key": "lm_chicago",
        "specific_location": "Chicago",
        "state_region": "Illinois",
        "country": "United States",
        "hierarchy": "Places|United States|Illinois|Chicago",
        "tags": ["Chicago", "Chicago Skyline", "Illinois", "Willis Tower", "Lake Michigan", "Skyscraper", "Cityscape"],
    },
    "venice_italy": {
        "probe_key": "lm_venice_italy",
        "specific_location": "Venice",
        "state_region": "Veneto",
        "country": "Italy",
        "hierarchy": "Places|Europe|Italy|Venice",
        "tags": ["Venice", "Italy", "Veneto", "Grand Canal", "Venetian Architecture", "Canal", "Europe"],
    },
    "colonial_doors_mexico": {
        "probe_key": "lm_colonial_doors",
        "specific_location": "San Miguel de Allende",
        "state_region": "Guanajuato",
        "country": "Mexico",
        "hierarchy": "Places|North America|Mexico|Colonial Architecture",
        "tags": ["Mexico", "San Miguel de Allende", "Oaxaca", "Doors", "Door", "Wooden Door", "Colonial Doors", "Colonial Architecture", "Courtyard", "Latin America"],
    },
}

FILLER_NOISE_WORDS: Set[str] = {
    "beautiful", "scenic", "artistic", "stunning", "nice", "lovely", "pretty",
    "amazing", "gorgeous", "wonderful", "awesome", "great", "fine art", "photograph",
    "photo", "image", "picture", "view", "scene", "unknown", "none", "not specified",
    "landscape", "to print", "mitch shooting", "alice", "west coast imaging*  alice",
    "west coast imaging* alice", "mitch rouse aerials", "aerials", "tripeast", "395",
    "keepers arch", "ranch", "structure", "structures", "human", "fauna", "flora",
}

JARGON_FACET_TAGS_LOWER: Set[str] = {
    "mountain peak", "canyon & mesa", "coastal shoreline", "river waterway", "lake & basin",
    "forest & woodland", "arid desert terrain", "ranch & pastureland", "barn & farmstead",
    "architectural facade", "industrial infrastructure", "urban architecture",
    "archway & courtyard", "wooden fence", "bridge & pier structure", "watercraft & boats",
    "rock formations", "botanical flora", "water surface & surf", "roadway & path",
    "cloud formations", "snow & glacial ice",
    "weathered wood texture", "stucco & masonry wall", "layered natural stone",
    "industrial metal & steel", "reflective water & ice", "textured earth & sand",
    "vibrant saturated color", "warm golden palette", "muted earth tones",
    "cool atmospheric tones", "natural color palette", "high-contrast monochrome",
    "centered symmetrical framing", "tight architectural detail", "wide panoramic vista",
    "leading lines geometry", "overhead geometric pattern", "layered landscape depth",
    "golden hour light", "soft diffused light", "crisp daylight sun",
    "dramatic storm light", "atmospheric mist & haze",
    "side_lighting", "diffused_light", "overcast_light", "natural_daylight", "soft_lighting",
    "hard_light", "backlighting", "golden_hour", "blue_hour", "morning_light", "evening_light",
    "dappled_light", "dramatic_lighting", "flat_lighting", "ambient_light", "studio_lighting",
    "high_contrast", "low_contrast", "shallow_depth_of_field", "deep_depth_of_field",
    "long_exposure", "wide_angle", "telephoto", "rule_of_thirds", "leading_lines",
    "symmetrical_composition", "minimalist_composition", "abstract_pattern",
    "g.d. eastlick grain elevator", "humphrey feed grain inc.", "nascar_hall_of_fame",
    "nascar hall of fame", "moma", "bryant park", "cleveland museum of art",
    "monon historic district", "buffalo way works", "lake_elberta", "lake elberta",
    "bolder basin", "working_cattle_ranch", "working cattle ranch", "desert_homestead",
    "desert homestead", "desert church", "silos on the illinois river", "two dot ranch",
    "keepers arch", "not specified",
}

HALLUCINATED_SPEC_LOCATIONS_LOWER: Set[str] = {
    "g.d. eastlick grain elevator",
    "humphrey feed grain inc.",
    "nascar_hall_of_fame",
    "nascar hall of fame",
    "moma",
    "bryant park",
    "cleveland museum of art",
    "monon historic district",
    "buffalo way works",
    "lake_elberta",
    "lake elberta",
    "bolder basin",
    "working_cattle_ranch",
    "working cattle ranch",
    "desert_homestead",
    "desert homestead",
    "desert church",
    "silos on the illinois river",
    "two dot ranch",
    "keepers arch",
    "not specified",
    "unknown",
    "landscape",
    "to print",
    "mitch shooting",
    "alice",
    "west coast imaging*  alice",
    "west coast imaging* alice",
    "tripeast",
    "ranch",
    "395",
}

_UNDERSCORE_SUBJECT_MAP: Dict[str, Optional[str]] = {
    "sandstone_butte": "Butte",
    "red_rock": "Red Rock",
    "desert_landscape": "Desert",
    "sand_dunes": "Sand Dunes",
    "mountain_range": "Mountains",
    "mountain_peaks": "Mountains",
    "snow_capped_mountains": "Mountains",
    "alpine_lake": "Alpine Lake",
    "sea_stacks": "Sea Stacks",
    "rocky_coastline": "Coastline",
    "ocean_waves": "Ocean & Surf",
    "sandy_beach": "Beach",
    "wooden_pier": "Pier",
    "grain_elevator": "Grain Elevator",
    "grain_silo": "Grain Silo",
    "weathered_barn": "Barn",
    "old_barn": "Barn",
    "wooden_barn": "Barn",
    "red_barn": "Barn",
    "farmhouse": "Homestead",
    "abandoned_building": "Homestead",
    "rolling_hills": "Rolling Hills",
    "wheat_fields": "Farmland",
    "agricultural_fields": "Farmland",
    "oil_pump_jack": "Oil Fields",
    "oil_field": "Oil Fields",
    "oil_refinery": "Oil Facility",
    "industrial_plant": "Industrial",
    "power_plant": "Power Plant",
    "cooling_towers": "Industrial",
    "freeway_interchange": "Bridges & Freeways",
    "highway_interchange": "Bridges & Freeways",
    "suspension_bridge": "Bridges & Freeways",
    "city_skyline": "Cityscape",
    "skyscrapers": "Skyscraper",
    "colonial_architecture": "Colonial Architecture",
    "wooden_door": "Doors & Windows",
    "arched_doorway": "Doors & Windows",
    "wrought_iron": "Architectural Detail",
    "stained_glass": "Architectural Detail",
    "spiral_staircase": "Staircase",
    "classic_car": "Classic Car",
    "vintage_car": "Classic Car",
    "wildflowers": "Wildflowers",
    "saguaro_cactus": "Cactus",
    "joshua_tree": "Joshua Tree",
    "cypress_trees": "Cypress Swamp",
    "autumn_foliage": "Autumn Trees",
    "aspen_trees": "Aspen Trees",
    "glacier_lagoon": "Glacial Ice & Black Sand",
    "icebergs": "Glacial Ice & Black Sand",
    "black_sand_beach": "Black Sand Beach",
    "basalt_columns": "Basalt Sea Stacks",
}

PORTFOLIO_CATEGORIES_CONFIG: List[Dict[str, Any]] = [
    {
        "category": "Desert",
        "icon": "🏜️",
        "description": "Monument Valley, Canyonlands, Valley of the Gods, Death Valley, Eastern Sierra & Southwest Deserts",
        "sub_regions": [
            "Monument Valley", "Canyonlands & Moab", "Valley of the Gods", "Death Valley",
            "Alabama Hills", "Eastern Sierra & Highway 395", "Mono Lake", "White Sands",
            "Anza-Borrego Desert", "Tucson & Sonoran Desert", "Joshua Tree", "Grand Canyon",
        ],
    },
    {
        "category": "Coastline & Piers",
        "icon": "🌊",
        "description": "California Piers, Big Sur, Point Lobos, Bandon Oregon Coast & Pacific Surf",
        "sub_regions": [
            "California Coast", "California Piers", "Big Sur", "Point Lobos",
            "Oregon Coast", "Bandon Coast", "Huntington Beach", "Ocean & Surf",
        ],
    },
    {
        "category": "Palouse & Farmland",
        "icon": "🌾",
        "description": "The Palouse, Rural Barns, Homesteads, Grain Elevators, Montana Plains & Wyoming Ranches",
        "sub_regions": [
            "Palouse", "Farmland", "Barns & Ranch", "Hawkeye Ranch & Southfork Valley",
            "Billings & Montana Plains", "Moccasin", "Humphrey, Nebraska",
        ],
    },
    {
        "category": "Oil Fields & Industrial",
        "icon": "🛢️",
        "description": "Taft Oil Field Aerials, Gulf Coast Energy Facilities & Industrial Infrastructure",
        "sub_regions": [
            "Oil Fields", "Taft Oil Field", "Industrial", "Oil Facility",
        ],
    },
    {
        "category": "National Parks & Mountains",
        "icon": "🏔️",
        "description": "Yosemite, Grand Tetons, Yellowstone, Grand Canyon, Everglades & Alpine Peaks",
        "sub_regions": [
            "Yosemite", "Grand Tetons", "Grand Canyon", "Yellowstone",
            "Everglades", "Mountains", "Lake Tahoe", "Bighorn Mountains",
        ],
    },
    {
        "category": "Iceland",
        "icon": "🇮🇸",
        "description": "Jökulsárlón Glacial Lagoon, Diamond Beach, Kirkjufell, Gullfoss, Reynisfjara & Reykjavík",
        "sub_regions": [
            "Iceland", "Jökulsárlón & Diamond Beach", "Kirkjufell Mountain",
            "Hallgrímskirkja, Reykjavík", "Gullfoss & Icelandic Waterfalls",
            "Reynisfjara Black Sand Beach", "Glacial Ice & Black Sand",
        ],
    },
    {
        "category": "Urban & Architecture",
        "icon": "🏙️",
        "description": "Chicago, Washington DC, Venice, San Miguel de Allende, Havana, Nashville, Savannah & Freeways",
        "sub_regions": [
            "Urban", "Chicago", "Washington DC", "Venice", "San Miguel de Allende",
            "Havana & Malecón", "Nashville", "Savannah, Georgia", "Bridges & Freeways",
        ],
    },
    {
        "category": "Still Life & Cultural Details",
        "icon": "🚪",
        "description": "Colonial Doors & Windows, Architectural Details, Courtyards, Artifacts & Botanical Studies",
        "sub_regions": [
            "Still Life", "Doors & Windows", "Colonial Architecture", "Wildflowers",
        ],
    },
    {
        "category": "Wildlife & Animals",
        "icon": "🦬",
        "description": "Bison, Horses, Cattle, Birds & Coastal Wildlife",
        "sub_regions": [
            "Wildlife", "Bison", "Horses & Cattle", "Birds",
        ],
    },
    {
        "category": "Pets & Animals",
        "icon": "🐾",
        "description": "Domestic Dogs, Cats, Pets & Indoor Companions",
        "sub_regions": [
            "Dog", "Cat", "Pet", "Pets", "Cat Tree",
        ],
    },
    {
        "category": "Portraits & People",
        "icon": "🧑",
        "description": "Portraits, Mirror Selfies, Friends, Family & Candid People",
        "sub_regions": [
            "Person", "Portrait", "Mirror Selfie", "Selfie", "Man", "Woman", "Family",
        ],
    },
    {
        "category": "Automotive & Urban",
        "icon": "🚗",
        "description": "Cars, Sports Cars, Sedans, Gas Stations, Night Street & Urban Scenes",
        "sub_regions": [
            "Car", "Sports Car", "Sedan", "Gas Station", "Automotive",
        ],
    },
    {
        "category": "Architecture & Interiors",
        "icon": "🏠",
        "description": "Indoor Living Spaces, Fitting Rooms, Interiors & Architectural Spaces",
        "sub_regions": [
            "Indoor", "Living Room", "Fitting Room", "Architecture",
        ],
    },
    {
        "category": "Everyday & Lifestyle",
        "icon": "📸",
        "description": "Everyday Personal Moments, Daily Life & Candid Snapshots",
        "sub_regions": [
            "Everyday", "Indoor", "Night",
        ],
    },
]

# Known Geographic & Domain Gazetteer for Natural-Language Teach Mode Parsing
_TEACH_GEO_GAZETTEER: Dict[str, Dict[str, Any]] = {
    "houma": {
        "city": "Houma",
        "state_region": "Louisiana",
        "country": "United States",
        "specific_location": "Houma, Louisiana",
        "tags": ["Houma", "Louisiana", "Gulf Coast", "Bayou Region"],
    },
    "louisiana": {
        "state_region": "Louisiana",
        "country": "United States",
        "tags": ["Louisiana", "Gulf Coast"],
    },
    "venice": {
        "city": "Venice",
        "state_region": "Veneto",
        "country": "Italy",
        "specific_location": "Venice, Italy",
        "tags": ["Venice", "Grand Canal", "Veneto", "Italy"],
    },
    "italy": {
        "country": "Italy",
        "tags": ["Italy", "European Architecture"],
    },
    "cuba": {
        "country": "Cuba",
        "state_region": "La Habana",
        "specific_location": "Havana & Malecón",
        "tags": ["Cuba", "Havana & Malecón", "Caribbean", "Colonial Architecture", "Latin America"],
    },
    "havana": {
        "city": "Havana",
        "state_region": "La Habana",
        "country": "Cuba",
        "specific_location": "Havana & Malecón",
        "tags": ["Havana", "Havana & Malecón", "Cuba", "Caribbean", "Colonial Architecture"],
    },
    "malecón": {
        "city": "Havana",
        "state_region": "La Habana",
        "country": "Cuba",
        "specific_location": "Havana & Malecón",
        "tags": ["Malecón", "Havana", "Havana & Malecón", "Cuba", "Caribbean"],
    },
    "malecon": {
        "city": "Havana",
        "state_region": "La Habana",
        "country": "Cuba",
        "specific_location": "Havana & Malecón",
        "tags": ["Malecón", "Havana", "Havana & Malecón", "Cuba", "Caribbean"],
    },
    "south america": {
        "country": "South America",
        "state_region": "South America",
        "specific_location": "South America",
        "tags": ["South America", "Latin America", "Colonial Architecture"],
    },
    "peru": {
        "country": "Peru",
        "state_region": "Cusco & Sacred Valley",
        "specific_location": "Peru",
        "tags": ["Peru", "Andes", "South America", "Colonial Architecture"],
    },
    "cusco": {
        "city": "Cusco",
        "state_region": "Cusco",
        "country": "Peru",
        "specific_location": "Cusco, Peru",
        "tags": ["Cusco", "Peru", "Andes", "South America", "Colonial Architecture"],
    },
    "argentina": {
        "country": "Argentina",
        "state_region": "Argentina",
        "specific_location": "Argentina",
        "tags": ["Argentina", "South America", "Latin America"],
    },
    "patagonia": {
        "country": "Argentina",
        "state_region": "Patagonia",
        "specific_location": "Patagonia",
        "tags": ["Patagonia", "Argentina", "Chile", "South America", "Andes", "Mountains"],
    },
    "chile": {
        "country": "Chile",
        "state_region": "Chile",
        "specific_location": "Chile",
        "tags": ["Chile", "South America", "Andes"],
    },
    "colombia": {
        "country": "Colombia",
        "state_region": "Colombia",
        "specific_location": "Colombia",
        "tags": ["Colombia", "South America", "Colonial Architecture", "Latin America"],
    },
    "brazil": {
        "country": "Brazil",
        "state_region": "Brazil",
        "specific_location": "Brazil",
        "tags": ["Brazil", "South America", "Latin America"],
    },
    "mexico": {
        "country": "Mexico",
        "state_region": "Guanajuato / Oaxaca",
        "specific_location": "Colonial Mexico",
        "tags": ["Mexico", "Colonial Mexico", "Colonial Architecture", "Latin America"],
    },
    "san miguel": {
        "city": "San Miguel de Allende",
        "state_region": "Guanajuato",
        "country": "Mexico",
        "specific_location": "San Miguel de Allende, Mexico",
        "tags": ["San Miguel de Allende", "Guanajuato", "Mexico", "Colonial Architecture"],
    },
    "oaxaca": {
        "city": "Oaxaca",
        "state_region": "Oaxaca",
        "country": "Mexico",
        "specific_location": "Oaxaca, Mexico",
        "tags": ["Oaxaca", "Mexico", "Colonial Architecture"],
    },
    "iceland": {
        "country": "Iceland",
        "state_region": "Iceland",
        "specific_location": "Iceland",
        "tags": ["Iceland", "Nordic Landscape", "Volcanic Terrain"],
    },
    "reykjavik": {
        "city": "Reykjavík",
        "state_region": "Capital Region",
        "country": "Iceland",
        "specific_location": "Hallgrímskirkja, Reykjavík",
        "tags": ["Reykjavík", "Hallgrímskirkja, Reykjavík", "Iceland"],
    },
    "utah": {"state_region": "Utah", "country": "United States", "tags": ["Utah", "American Southwest"]},
    "arizona": {"state_region": "Arizona", "country": "United States", "tags": ["Arizona", "American Southwest"]},
    "california": {"state_region": "California", "country": "United States", "tags": ["California"]},
    "wyoming": {"state_region": "Wyoming", "country": "United States", "tags": ["Wyoming"]},
    "montana": {"state_region": "Montana", "country": "United States", "tags": ["Montana"]},
    "colorado": {"state_region": "Colorado", "country": "United States", "tags": ["Colorado"]},
    "washington": {"state_region": "Washington", "country": "United States", "tags": ["Washington", "Pacific Northwest"]},
    "oregon": {"state_region": "Oregon", "country": "United States", "tags": ["Oregon", "Pacific Northwest"]},
    "new mexico": {"state_region": "New Mexico", "country": "United States", "tags": ["New Mexico", "American Southwest"]},
    "texas": {"state_region": "Texas", "country": "United States", "tags": ["Texas"]},
    "florida": {"state_region": "Florida", "country": "United States", "tags": ["Florida"]},
    "illinois": {"state_region": "Illinois", "country": "United States", "tags": ["Illinois"]},
    "chicago": {"city": "Chicago", "state_region": "Illinois", "country": "United States", "specific_location": "Chicago, Illinois", "tags": ["Chicago", "Illinois"]},
    "tucson": {"city": "Tucson", "state_region": "Arizona", "country": "United States", "specific_location": "Tucson, Arizona", "tags": ["Tucson", "Arizona", "Sonoran Desert"]},
    "taft": {"city": "Taft", "state_region": "California", "country": "United States", "specific_location": "Taft Oil Field, California", "tags": ["Taft Oil Field", "Kern County", "California"]},
    "palouse": {"state_region": "Washington", "country": "United States", "specific_location": "The Palouse, Washington", "tags": ["Palouse", "Rolling Hills", "Washington"]},
    "monument valley": {"state_region": "Arizona", "country": "United States", "specific_location": "Monument Valley", "tags": ["Monument Valley", "Butte", "Buttes", "Arizona", "Utah"]},
    "valley of the gods": {"state_region": "Utah", "country": "United States", "specific_location": "Valley of the Gods, Utah", "tags": ["Valley of the Gods", "Butte", "Buttes", "Utah"]},
}

_TEACH_SUBJECT_CONCEPTS: Dict[str, List[str]] = {
    "oil facility": ["Oil Facility", "Industrial Facility", "Energy Infrastructure", "Oil & Gas", "Industrial"],
    "oil refinery": ["Oil Refinery", "Oil Facility", "Industrial Facility", "Energy Infrastructure", "Industrial"],
    "oil field": ["Oil Field", "Oil Facility", "Energy Infrastructure", "Industrial"],
    "industrial": ["Industrial", "Industrial Facility", "Industrial Infrastructure"],
    "power plant": ["Power Plant", "Industrial Facility", "Energy Infrastructure"],
    "door": ["Door", "Doors", "Doors & Windows", "Wooden Door"],
    "doors": ["Doors", "Door", "Doors & Windows", "Wooden Door"],
    "window": ["Window", "Windows", "Doors & Windows"],
    "windows": ["Windows", "Window", "Doors & Windows"],
    "horse": ["Horse", "Horses", "Equine", "Animal", "Animals", "Wildlife"],
    "horses": ["Horses", "Horse", "Equine", "Animal", "Animals", "Wildlife"],
    "bison": ["Bison", "Buffalo", "Wildlife", "Animal", "Animals"],
    "buffalo": ["Buffalo", "Bison", "Wildlife", "Animal", "Animals"],
    "cattle": ["Cattle", "Cow", "Cows", "Livestock", "Animal", "Animals"],
    "barn": ["Barn", "Barns & Ranch", "Farmstead", "Building"],
    "ranch": ["Barns & Ranch", "Pasture", "Rural"],
    "butte": ["Butte", "Buttes", "Sandstone Butte", "Desert Monolith"],
    "buttes": ["Buttes", "Butte", "Sandstone Butte", "Desert Monolith"],
    "church": ["Church", "Cathedral", "Architecture", "Building"],
    "bridge": ["Bridge", "Bridges & Freeways", "Span", "Infrastructure"],
    "pier": ["Pier", "Coastline & Piers", "Coast"],
    "boat": ["Boat", "Boats", "Watercraft", "Maritime"],
    "boats": ["Boats", "Boat", "Watercraft", "Maritime"],
    "bayou": ["Bayou", "Wetlands", "Marsh", "Waterway", "Cypress Swamp"],
    "dog": ["Dog", "Pet", "Canine", "Animal"],
    "cat": ["Cat", "Pet", "Feline", "Animal"],
    "feline": ["Feline", "Cat", "Pet"],
    "cat tree": ["Cat Tree", "Indoor", "Pet"],
    "bee": ["Bee", "Insect", "Macro Photography", "Still Life"],
    "bees": ["Bee", "Insect", "Macro Photography", "Still Life"],
    "honeybee": ["Bee", "Insect", "Macro Photography", "Still Life"],
    "honeybees": ["Bee", "Insect", "Macro Photography", "Still Life"],
    "bumblebee": ["Bee", "Insect", "Macro Photography", "Still Life"],
    "wasp": ["Wasp", "Insect", "Macro Photography", "Still Life"],
    "insect": ["Insect", "Macro Photography", "Still Life"],
    "insects": ["Insect", "Macro Photography", "Still Life"],
    "macro": ["Macro Photography", "Still Life"],
    "macro photography": ["Macro Photography", "Still Life"],
    "macro stacked": ["Macro Photography", "Focus Stacked Macro", "Still Life"],
    "focus stacked": ["Macro Photography", "Focus Stacked Macro", "Still Life"],
    "focus stack": ["Macro Photography", "Focus Stacked Macro", "Still Life"],
    "focus stacking": ["Macro Photography", "Focus Stacked Macro", "Still Life"],
    "mirror selfie": ["Mirror Selfie", "Selfie", "Person", "Portrait"],
    "selfie": ["Selfie", "Mirror Selfie", "Person", "Portrait"],
    "fitting room": ["Fitting Room", "Indoor", "Mirror"],
    "car": ["Car", "Automobile"],
    "sports car": ["Sports Car", "Car", "Sedan", "Automobile"],
    "sedan": ["Sedan", "Car", "Sports Car", "Automobile"],
    "lexus": ["Lexus", "Sports Car", "Sedan", "Car"],
    "gas station": ["Gas Station", "Gas Pump", "Automotive"],
}

# Safelist of valid generic visual nouns that should NEVER be added to negated_tags
# during a Clean-Slate Wipe & Re-Anchor (unless the user explicitly says "not <noun>").
_GENERIC_VISUAL_NOUNS_KEEP: Set[str] = {
    "door", "doors", "doors & windows", "wooden door", "window", "windows",
    "building", "buildings", "architecture", "facade", "courtyard", "archway", "staircase",
    "street", "alley", "plaza", "balcony", "wall", "roof", "church", "cathedral",
    "bridge", "bridges & freeways", "pier", "road", "highway", "freeway",
    "water", "ocean", "ocean & surf", "sea", "coast", "coastline", "coastline & piers",
    "beach", "wave", "waves", "surf", "river", "lake", "waterfall", "reflection",
    "boat", "boats", "sailboat", "ship", "harbor", "watercraft",
    "tree", "trees", "forest", "palm tree", "wildflowers", "flower", "flowers", "cactus",
    "mountain", "mountains", "peak", "peaks", "hill", "hills", "rolling hills",
    "canyon", "butte", "buttes", "rock", "rocks", "cliff", "cliffs", "desert", "dunes", "sand dunes",
    "sky", "clouds", "sunset", "sunrise", "fog", "mist", "snow", "snow & ice", "ice",
    "barn", "barns & ranch", "homestead", "farmhouse", "fence", "corral", "farmland",
    "grain elevator", "grain silo", "windmill",
    "horse", "horses", "horses & cattle", "cattle", "cow", "cows", "bison", "buffalo",
    "bird", "birds", "dog", "dogs", "cat", "cats", "pet", "pets", "cat tree", "scratching post",
    "scottish fold", "british shorthair", "american shorthair", "tabby cat", "orange tabby",
    "black cat", "tuxedo cat", "calico", "tortoiseshell", "siamese", "ragdoll",
    "maine coon / longhair", "bengal", "persian",
    "chihuahua", "rat terrier", "jack russell terrier", "french bulldog", "english bulldog",
    "corgi", "dachshund", "beagle", "golden retriever", "labrador retriever", "german shepherd",
    "australian shepherd", "border collie", "poodle / doodle", "siberian husky", "boxer",
    "pit bull terrier", "pomeranian", "spaniel",
    "wildlife", "wildlife & animals", "animal", "animals",
    "bee", "bees", "honeybee", "honeybees", "bumblebee", "wasp", "insect", "insects",
    "macro", "macro photography", "focus stacked", "focus stack", "focus stacked macro",
    "person", "people", "man", "woman", "portrait", "mirror selfie", "selfie", "fitting room",
    "living room", "carpet", "area rug / carpet", "couch", "bohemian tapestry / woven throw",
    "framed art", "modern / pop wall art", "decorative lamp", "indoor",
    "photographer", "mitch rouse (subject)",
    "classic car", "car", "cars", "sports car", "sedan", "lexus", "automobile",
    "gas station", "gas pump", "night", "artificial lighting", "train", "railroad",
    "aerial", "terrestrial", "still life", "still life & cultural details", "urban", "urban & architecture",
} | {str(item["tag"]).strip().lower() for item in SPECIALIST_DRILLDOWN_TAXONOMY}

# Canonical Singular / Plural Tag Pairs — Never emit both on the same image.
US_STATE_NAMES: Set[str] = {
    "Alabama", "Alaska", "Arizona", "Arkansas", "California", "Colorado", "Connecticut",
    "Delaware", "Florida", "Georgia", "Hawaii", "Idaho", "Illinois", "Indiana", "Iowa",
    "Kansas", "Kentucky", "Louisiana", "Maine", "Maryland", "Massachusetts", "Michigan",
    "Minnesota", "Mississippi", "Missouri", "Montana", "Nebraska", "Nevada", "New Hampshire",
    "New Jersey", "New Mexico", "New York", "North Carolina", "North Dakota", "Ohio",
    "Oklahoma", "Oregon", "Pennsylvania", "Rhode Island", "South Carolina", "South Dakota",
    "Tennessee", "Texas", "Utah", "Vermont", "Virginia", "Washington", "West Virginia",
    "Wisconsin", "Wyoming",
}

SINGULAR_PLURAL_PAIRS: List[Tuple[str, str]] = [
    ("Bird", "Birds"),
    ("Boat", "Boats"),
    ("Dog", "Dogs"),
    ("Cat", "Cats"),
    ("Frog", "Frogs"),
    ("Horse", "Horses"),
    ("Quarter Horse", "Quarter Horses"),
    ("Cow", "Cows"),
    ("Pelican", "Pelicans"),
    ("Goose", "Geese"),
    ("Duck", "Ducks"),
    ("Animal", "Animals"),
    ("Person", "People"),
    ("Man", "Men"),
    ("Woman", "Women"),
    ("Child", "Children"),
    ("Cowboy", "Cowboys"),
    ("Door", "Doors"),
    ("Window", "Windows"),
    ("Butte", "Buttes"),
    ("Tree", "Trees"),
    ("Mountain", "Mountains"),
    ("Building", "Buildings"),
    ("Car", "Cars"),
    ("Flower", "Flowers"),
    ("Wildflower", "Wildflowers"),
    ("Poppy", "Poppies"),
    ("Cactus", "Cacti"),
]

# Discrete countable subjects that MUST pass Contrastive Habitat & Artifact Foil Gating
# (or come from explicit human-taught tags / non-place .lrcat subject keywords) before tagging.
COUNTABLE_DISCRETE_SUBJECT_TAGS_LOWER: Set[str] = {
    "bird", "birds", "avian", "pelican", "pelicans", "eagle", "bald eagle", "hawk",
    "osprey", "owl", "heron", "egret", "crane", "sandhill crane", "goose", "geese",
    "snow geese", "duck", "ducks", "waterfowl", "gull", "seagull", "seabird", "raptor", "wading_bird",
    "frog", "frogs", "toad", "amphibian",
    "dog", "dogs", "canine", "puppy", "chihuahua",
    "cat", "cats", "feline", "kitten",
    "horse", "horses", "quarter horse", "quarter horses", "stallion", "mare", "foal", "mustang", "equine",
    "cattle", "cow", "cows", "black angus", "bull", "steer", "calf", "longhorn", "livestock", "horses & cattle",
    "bison", "buffalo", "american bison",
    "deer", "mule deer", "elk", "moose", "pronghorn", "antelope", "bighorn", "bighorn sheep", "sheep",
    "bear", "grizzly", "grizzly bear", "coyote", "wolf", "fox", "alligator", "whale", "dolphin", "seal", "sea lion",
    "wildlife", "wildlife & animals", "animal", "animals",
    "bee", "bees", "honeybee", "honeybees", "bumblebee", "wasp", "insect", "insects",
    "macro", "macro photography", "focus stacked", "focus stack", "focus stacked macro", "fauna", "mammals", "ungulates", "pet", "pets",
    "person", "people", "human", "individual", "man", "men", "male", "woman", "women", "female",
    "boy", "girl", "child", "children", "youth", "adult", "family", "portrait", "mirror selfie", "selfie",
    "photographer", "mitch rouse (subject)", "cowboy", "cowboys", "rancher", "wrangler",
    "rider", "horseback rider", "worker", "farmer", "pilot", "hiker", "surfer",
    "boat", "boats", "sailboat", "ship", "watercraft", "vessel", "watercraft & boats",
    "car", "cars", "classic car", "sports car", "sedan", "lexus", "automobile", "truck",
    "train", "locomotive", "airplane", "aircraft", "helicopter",
}

# Search queries targeting countable discrete subjects -> required verified tag set (lowercase)
COUNTABLE_SEARCH_CONCEPTS: Dict[str, Set[str]] = {
    "bird": {"bird", "birds", "pelican", "pelicans", "eagle", "bald eagle", "hawk", "osprey", "owl", "heron", "egret", "crane", "sandhill crane", "goose", "geese", "snow geese", "duck", "ducks", "waterfowl", "gull", "seagull"},
    "birds": {"bird", "birds", "pelican", "pelicans", "eagle", "bald eagle", "hawk", "osprey", "owl", "heron", "egret", "crane", "sandhill crane", "goose", "geese", "snow geese", "duck", "ducks", "waterfowl", "gull", "seagull"},
    "pelican": {"pelican", "pelicans"},
    "pelicans": {"pelican", "pelicans"},
    "eagle": {"eagle", "bald eagle"},
    "eagles": {"eagle", "bald eagle"},
    "hawk": {"hawk"},
    "hawks": {"hawk"},
    "owl": {"owl"},
    "owls": {"owl"},
    "heron": {"heron", "egret"},
    "crane": {"crane", "sandhill crane"},
    "cranes": {"crane", "sandhill crane"},
    "goose": {"goose", "geese", "snow geese"},
    "geese": {"goose", "geese", "snow geese"},
    "duck": {"duck", "ducks", "waterfowl"},
    "ducks": {"duck", "ducks", "waterfowl"},
    "frog": {"frog", "frogs", "toad", "amphibian"},
    "frogs": {"frog", "frogs", "toad", "amphibian"},
    "toad": {"frog", "frogs", "toad", "amphibian"},
    "alligator": {"alligator"},
    "alligators": {"alligator"},
    "dog": {
        "dog", "dogs", "canine", "puppy", "chihuahua", "rat terrier", "jack russell terrier",
        "french bulldog", "english bulldog", "corgi", "dachshund", "beagle", "golden retriever",
        "labrador retriever", "german shepherd", "australian shepherd", "border collie",
        "poodle / doodle", "siberian husky", "boxer", "pit bull terrier", "pomeranian", "spaniel",
    },
    "dogs": {
        "dog", "dogs", "canine", "puppy", "chihuahua", "rat terrier", "jack russell terrier",
        "french bulldog", "english bulldog", "corgi", "dachshund", "beagle", "golden retriever",
        "labrador retriever", "german shepherd", "australian shepherd", "border collie",
        "poodle / doodle", "siberian husky", "boxer", "pit bull terrier", "pomeranian", "spaniel",
    },
    "cat": {
        "cat", "cats", "feline", "kitten", "scottish fold", "british shorthair", "american shorthair",
        "tabby cat", "orange tabby", "black cat", "tuxedo cat", "calico", "tortoiseshell",
        "siamese", "ragdoll", "maine coon / longhair", "bengal", "persian",
    },
    "cats": {
        "cat", "cats", "feline", "kitten", "scottish fold", "british shorthair", "american shorthair",
        "tabby cat", "orange tabby", "black cat", "tuxedo cat", "calico", "tortoiseshell",
        "siamese", "ragdoll", "maine coon / longhair", "bengal", "persian",
    },
    "scottish fold": {"scottish fold"},
    "french bulldog": {"french bulldog"},
    "chihuahua": {"chihuahua", "rat terrier"},
    "pet": {
        "pet", "pets", "dog", "dogs", "cat", "cats", "puppy", "kitten", "scottish fold",
        "french bulldog", "chihuahua", "rat terrier",
    },
    "pets": {
        "pet", "pets", "dog", "dogs", "cat", "cats", "puppy", "kitten", "scottish fold",
        "french bulldog", "chihuahua", "rat terrier",
    },
    "selfie": {"selfie", "mirror selfie"},
    "mirror selfie": {"mirror selfie", "selfie"},
    "horse": {"horse", "horses", "quarter horse", "quarter horses", "stallion", "mare", "foal", "mustang", "equine"},
    "horses": {"horse", "horses", "quarter horse", "quarter horses", "stallion", "mare", "foal", "mustang", "equine"},
    "cattle": {"cattle", "cow", "cows", "black angus", "bull", "steer", "calf", "longhorn", "livestock"},
    "cow": {"cattle", "cow", "cows", "black angus", "bull", "steer", "calf", "longhorn"},
    "cows": {"cattle", "cow", "cows", "black angus", "bull", "steer", "calf", "longhorn"},
    "bison": {"bison", "buffalo", "american bison"},
    "buffalo": {"bison", "buffalo", "american bison"},
    "deer": {"deer", "mule deer"},
    "elk": {"elk"},
    "bear": {"bear", "grizzly", "grizzly bear"},
    "bears": {"bear", "grizzly", "grizzly bear"},
    "wildlife": {"wildlife", "bison", "buffalo", "bird", "birds", "pelican", "pelicans", "eagle", "hawk", "owl", "heron", "egret", "crane", "goose", "geese", "duck", "ducks", "deer", "elk", "moose", "pronghorn", "bighorn sheep", "bear", "grizzly bear", "coyote", "wolf", "fox", "alligator", "whale", "dolphin", "seal", "sea lion", "frog", "frogs"},
    "animal": {"animal", "animals", "wildlife", "bison", "buffalo", "horse", "horses", "cattle", "cow", "cows", "dog", "dogs", "cat", "cats", "pet", "pets", "bird", "birds", "deer", "elk", "bear", "frog", "frogs", "sheep"},
    "animals": {"animal", "animals", "wildlife", "bison", "buffalo", "horse", "horses", "cattle", "cow", "cows", "dog", "dogs", "cat", "cats", "pet", "pets", "bird", "birds", "deer", "elk", "bear", "frog", "frogs", "sheep"},
    "person": {"person", "people", "man", "men", "woman", "women", "boy", "girl", "child", "children", "family", "portrait", "mirror selfie", "selfie", "photographer", "mitch rouse (subject)", "cowboy", "cowboys", "rancher", "rider"},
    "people": {"person", "people", "man", "men", "woman", "women", "boy", "girl", "child", "children", "family", "portrait", "mirror selfie", "selfie", "photographer", "mitch rouse (subject)", "cowboy", "cowboys", "rancher", "rider"},
    "man": {"man", "men", "male", "cowboy", "cowboys", "mitch rouse (subject)"},
    "men": {"man", "men", "male", "cowboy", "cowboys", "mitch rouse (subject)"},
    "woman": {"woman", "women", "female", "girl"},
    "women": {"woman", "women", "female", "girl"},
    "boat": {"boat", "boats", "sailboat", "ship", "watercraft", "vessel"},
    "boats": {"boat", "boats", "sailboat", "ship", "watercraft", "vessel"},
    "car": {"car", "cars", "classic car", "sports car", "sedan", "lexus", "automobile", "truck"},
    "cars": {"car", "cars", "classic car", "sports car", "sedan", "lexus", "automobile", "truck"},
    "sports car": {"sports car", "sedan", "lexus", "car"},
    "sedan": {"sedan", "sports car", "lexus", "car"},
    "train": {"train", "locomotive", "railroad"},
    "trains": {"train", "locomotive", "railroad"},
    "airplane": {"airplane", "aircraft", "helicopter"},
}


def deduplicate_singular_plural_tags(
    tags: List[str],
    subject_counts: Optional[Dict[str, int]] = None,
) -> List[str]:
    """
    Ensures a photo NEVER carries both singular and plural variants of the same concept
    (e.g., never both 'Boat' and 'Boats', 'Bird' and 'Birds', 'Butte' and 'Buttes').
    When subject_counts provides a verified instance count for the concept:
      - count == 1 -> canonical Singular form
      - count >= 2 -> canonical Plural form
    When both forms exist without an explicit count, keeps the first-occurring form
    (or singular for single-subject defaults) and drops the duplicate form.
    """
    if not tags:
        return []
    counts = {str(k).strip().lower(): int(v) for k, v in (subject_counts or {}).items() if v is not None}

    # Build lookup from lower tag -> (singular_canon, plural_canon)
    pair_map: Dict[str, Tuple[str, str]] = {}
    for sing, plur in SINGULAR_PLURAL_PAIRS:
        pair_map[sing.lower()] = (sing, plur)
        pair_map[plur.lower()] = (sing, plur)

    # First pass: determine winning form for each pair present in tags
    present_lowers = {str(t).strip().lower() for t in tags if str(t).strip()}
    winning_form_by_pair: Dict[Tuple[str, str], str] = {}

    for sing, plur in SINGULAR_PLURAL_PAIRS:
        s_low, p_low = sing.lower(), plur.lower()
        has_s = s_low in present_lowers
        has_p = p_low in present_lowers
        if not has_s and not has_p:
            continue
        cnt = counts.get(s_low) or counts.get(p_low)
        if cnt is not None:
            winning_form_by_pair[(sing, plur)] = plur if cnt >= 2 else sing
        elif has_s and has_p:
            # Prefer singular for discrete animals/people/objects unless plural was first and no singular count
            first_seen = None
            for t in tags:
                tl = str(t).strip().lower()
                if tl == s_low:
                    first_seen = sing
                    break
                if tl == p_low:
                    first_seen = plur
                    break
            winning_form_by_pair[(sing, plur)] = first_seen or sing
        elif has_s:
            winning_form_by_pair[(sing, plur)] = sing
        else:
            winning_form_by_pair[(sing, plur)] = plur

    # Second pass: rewrite/filter tags preserving order without duplicates
    out: List[str] = []
    seen_low: Set[str] = set()
    for t in tags:
        clean_t = str(t).strip()
        if not clean_t:
            continue
        tl = clean_t.lower()
        if tl in pair_map:
            pair = pair_map[tl]
            winner = winning_form_by_pair.get(pair, clean_t)
            wl = winner.lower()
            if wl not in seen_low:
                seen_low.add(wl)
                out.append(winner)
        else:
            if tl not in seen_low:
                seen_low.add(tl)
                out.append(clean_t)
    return out

