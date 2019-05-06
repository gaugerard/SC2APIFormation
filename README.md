# SC2APIFormation
Code de la formation sur la librairie Python sc2api.

Librairie a importer:
    - sc2
    - sc2ai

pour installer les packages dont le Bot a besoin, taper ceci
dans la console :

    pip install -r requirements.txt

/!\ 1) il faut vérifier que le chemin vers le dossier du jeu Starcraft 2 est correct dans
       "site-package/sc2/paths.py". s'il le faut, modifiez la ligne ci dessous.

                "Windows": "C:/Program Files (x86)/StarCraft II",

    2) Vous devez utiliser une version de Pycharm antérieur à 2019.01

    3) il faut commenter avec "#" la ligne 9 dans site-packages/sc2/pixal-map.py