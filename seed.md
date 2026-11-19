py -X utf8 scripts/download_public.py
py -X utf8 scripts/run_lab.py --seeds 83
py -X utf8 scripts/inject_release.py --seed 11 --out runs/r11
py -X utf8 scripts/inject_release.py --seed 22 --out runs/r22
py -X utf8 scripts/inject_release.py --seed 5 --no-faults --out runs/clean
