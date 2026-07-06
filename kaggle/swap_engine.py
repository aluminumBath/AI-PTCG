#!/usr/bin/env python3
"""Swap the bundled sample engine for the official competition `cg/` and rebuild
a FLAT, verified submission.tar.gz.

You run this once you've downloaded the official engine from the competition Data
tab. It validates the official engine actually loads, replaces the bundled cg/
(backing up the old one), rebuilds the tarball with a flat layout (no wrapper
folder, no macOS/`__pycache__` junk), and then verifies the tarball by extracting
it and playing a full game with the NEW engine before declaring success.

    python3 swap_engine.py /path/to/official/cg
    python3 swap_engine.py /path/to/official/cg --submission-dir ptcg-sim-submission

If the official engine ships as a zip, unzip it first so you have a folder that
contains cg/ (i.e. the path you pass should be the directory that holds api.py,
game.py, and the compiled libcg.so / cg.dll).
"""
import argparse
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile

BUNDLE_ITEMS = ["main.py", "deck.csv", "cg", "README.md"]
SKIP = {".DS_Store", "__pycache__"}


def die(msg):
    print(f"\n[ABORT] {msg}")
    sys.exit(1)


def find_cg(path):
    """Accept the engine dir under any name (as long as it has api.py), or a
    parent that contains a cg/ engine dir."""
    path = os.path.abspath(path)
    if os.path.isdir(path) and os.path.exists(os.path.join(path, "api.py")):
        return path
    inner = os.path.join(path, "cg")
    if os.path.isdir(inner) and os.path.exists(os.path.join(inner, "api.py")):
        return inner
    die(f"no engine folder (containing api.py) found at {path}")


def has_compiled_lib(cg_dir):
    return any(f.startswith("libcg") or f in ("cg.dll", "cg.pyd") or f.endswith(".so")
              for f in os.listdir(cg_dir))


def load_test(cg_dir):
    """Import the official engine in a subprocess and load the card DB. Staged as
    `cg` in a temp dir so the source folder name doesn't matter."""
    with tempfile.TemporaryDirectory() as tmp:
        staged = os.path.join(tmp, "cg")
        shutil.copytree(cg_dir, staged,
                        ignore=shutil.ignore_patterns(*SKIP, "._*"))
        env = dict(os.environ, PYTHONPATH=tmp, PTCG_OFFLINE="1")
        code = ("import cg; from cg.api import all_card_data, all_attack; "
                "print(len(all_card_data()), len(all_attack()))")
        r = subprocess.run([sys.executable, "-c", code], env=env,
                           capture_output=True, text=True)
        if r.returncode != 0:
            die("official engine failed to import / load cards:\n"
                + (r.stderr or r.stdout))
        return r.stdout.strip()


def add_flat(tar, root):
    """Add the four bundle items to the tar at the archive root (flat)."""
    for item in BUNDLE_ITEMS:
        src = os.path.join(root, item)
        if not os.path.exists(src):
            die(f"missing bundle item: {item}")
        if os.path.isfile(src):
            tar.add(src, arcname=item)
        else:
            for dirpath, dirnames, filenames in os.walk(src):
                dirnames[:] = [d for d in dirnames if d not in SKIP]
                for fn in filenames:
                    if fn in SKIP or fn.startswith("._"):
                        continue
                    full = os.path.join(dirpath, fn)
                    arc = os.path.join(item, os.path.relpath(full, src))
                    tar.add(full, arcname=arc)


def verify_tar(tar_path):
    """Extract the tarball and play one full game with the bundled engine."""
    with tempfile.TemporaryDirectory() as tmp:
        with tarfile.open(tar_path) as t:
            names = t.getnames()
            if "main.py" not in names or "cg/api.py" not in names:
                die(f"tarball is not flat (expected main.py & cg/api.py at root): {names[:5]}")
            t.extractall(tmp)
        code = (
            "import os; os.environ['PTCG_OFFLINE']='1'\n"
            "import main as A\n"
            "from cg.game import battle_start, battle_select, battle_finish\n"
            "deck=[int(x) for x in open('deck.csv').read().split() if x.strip()]\n"
            "obs=battle_start(deck,deck)[0]; n=0; res=None\n"
            "while obs is not None and n<4000:\n"
            "    cur=obs.get('current')\n"
            "    if cur is not None and cur.get('result',-1) not in (None,-1): res=cur['result']; break\n"
            "    obs=battle_select(A.agent(obs)); n+=1\n"
            "battle_finish()\n"
            "print('GAME_OK result=%s steps=%s'%(res,n))\n"
        )
        env = dict(os.environ, PYTHONPATH=tmp, PTCG_OFFLINE="1")
        r = subprocess.run([sys.executable, "-c", code], cwd=tmp, env=env,
                           capture_output=True, text=True)
        if r.returncode != 0 or "GAME_OK" not in r.stdout:
            die("tarball failed to play a game with the new engine:\n"
                + (r.stderr or r.stdout))
        return r.stdout.strip()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("official_cg", help="path to the official cg/ folder (or its parent)")
    ap.add_argument("--submission-dir", default=None,
                    help="submission folder (default: ./ptcg-sim-submission or the "
                         "folder this script lives next to)")
    args = ap.parse_args()

    here = os.path.dirname(os.path.abspath(__file__))
    sub = args.submission_dir or (
        "ptcg-sim-submission" if os.path.isdir("ptcg-sim-submission")
        else os.path.join(here, "ptcg-sim-submission"))
    sub = os.path.abspath(sub)
    if not os.path.isdir(sub):
        die(f"submission dir not found: {sub}")

    official = find_cg(args.official_cg)
    print(f"official engine: {official}")
    if not has_compiled_lib(official):
        print("  [warn] no compiled lib (libcg.so / cg.dll) seen -- continuing, but "
              "the official engine normally ships one.")

    cur_cg = os.path.join(sub, "cg")
    off_files = sorted(f for f in os.listdir(official) if f not in SKIP)
    if os.path.isdir(cur_cg):
        cur_files = sorted(f for f in os.listdir(cur_cg) if f not in SKIP)
        if set(off_files) != set(cur_files):
            print(f"  [note] file set differs from the bundled sample engine:")
            print(f"         official only: {sorted(set(off_files)-set(cur_files))}")
            print(f"         sample only:   {sorted(set(cur_files)-set(off_files))}")

    print("validating official engine (import + load cards)...")
    counts = load_test(official)
    print(f"  loaded OK: {counts} (cards, attacks)")

    if os.path.isdir(cur_cg):
        bak = os.path.join(sub, "cg.sample.bak")
        if os.path.exists(bak):
            shutil.rmtree(bak)
        shutil.move(cur_cg, bak)
        print(f"  backed up sample engine -> {os.path.relpath(bak, sub)}")
    shutil.copytree(official, cur_cg)
    print(f"  installed official engine -> {os.path.relpath(cur_cg, sub)}")

    tar_path = os.path.join(sub, "submission.tar.gz")
    if os.path.exists(tar_path):
        os.remove(tar_path)
    with tarfile.open(tar_path, "w:gz") as t:
        add_flat(t, sub)
    size = os.path.getsize(tar_path) / 1e6
    print(f"rebuilt {os.path.relpath(tar_path, sub)} ({size:.2f} MB, flat)")

    print("verifying tarball (extract + play a full game with the new engine)...")
    print("  " + verify_tar(tar_path))
    print(f"\n[DONE] {tar_path} is ready to upload.")


if __name__ == "__main__":
    main()
