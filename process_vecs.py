import pickle
import sqlite3
import sys
from typing import Set

import numpy as np
from numpy.lib.format import open_memmap


def valid_guess(s: str) -> bool:
    if all(c.isalpha() or c in '.-' for c in s):
        return any(c.isalpha() for c in s)
    else:
        return False


def only_normal_letters(word: str, allow_capitalization: bool = False) -> bool:
    lowers = set(c for c in 'abcdefghijklmnopqrstuvwxyzäöǘß')
    uppers = set(c for c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÜẞ')
    both = lowers.union(uppers)
    if allow_capitalization:
        return all(c in both for c in word)
    else:
        return all(c in lowers for c in word)


def load_dic(path: str, allow_capitalization: bool = False) -> Set[str]:
    rtn = set()
    with open(path, 'r', encoding='utf-16') as f:
        for line in f.readlines():
            word = line.strip()
            if only_normal_letters(word, allow_capitalization):
                rtn.add(word)
    # april fools and early guesses
    extras = ['vereinbarung', 'aha', 'tja', 'ah', 'äh']
    rtn.update(extras)
    return rtn


if __name__ == '__main__':
    skip_db = len(sys.argv) > 1 and sys.argv[1] == '-s'
    if skip_db:
        print('skipping db writing')

    normal_words = load_dic('data/de.dic', True)
    print("# words in dictionary:", len(normal_words))

    # Pass 1: count how many rows the valid_nearest matrix will have so we can
    # pre-allocate the memmap at exactly the right size. Only parses the first
    # token of each line, so it is fast and very low on memory.
    print("pass 1: counting valid_nearest rows...")
    valid_count = 0
    with open('data/cc.de.300.vec', 'r', encoding='utf-8') as w2v_file:
        _ = w2v_file.readline()
        for n, line in enumerate(w2v_file):
            word = line.partition(' ')[0]
            if word in normal_words:
                valid_count += 1
            if n and n % 500000 == 0:
                print(f"  pass 1: scanned {n} lines, {valid_count} valid so far")
    print(f"pass 1 done: {valid_count} valid_nearest rows")

    # .npy-format memmap: written straight to disk as float32, so peak RAM
    # stays low and semantle.py can later np.load(..., mmap_mode='r') without
    # reading the whole matrix into memory.
    valid_nearest_mat = open_memmap(
        'data/valid_nearest_mat.npy',
        mode='w+',
        dtype=np.float32,
        shape=(valid_count, 300),
    )
    valid_nearest_words = []

    connection = sqlite3.connect('data/valid_guesses.db')
    cursor = connection.cursor()
    cursor.execute("""CREATE TABLE IF NOT EXISTS guesses (word text PRIMARY KEY, vec blob)""")
    print("created table")

    print("pass 2: parsing vectors...")
    eliminated = 0
    with open('data/cc.de.300.vec', 'r', encoding='utf-8') as w2v_file:
        _ = w2v_file.readline()
        for n, line in enumerate(w2v_file):
            # careful! some data sets (e.g. dewiki100.txt) have non-breaking spaces, which get split
            # others have trailing spaces (e.g. COW.token.wang2vec), meaning an empty string is included with split(' ')
            words = line.rstrip().split(' ')
            word = words[0]
            vec = np.array([float(w1) for w1 in words[1:]], dtype=np.float32)
            if word in normal_words:
                valid_nearest_mat[len(valid_nearest_words)] = vec
                valid_nearest_words.append(word)
            if valid_guess(word) and not skip_db:
                # INSERT OR IGNORE: cc.de.300.vec occasionally contains the same
                # token twice (differently-encoded whitespace splits), which
                # would crash a plain INSERT on the UNIQUE word constraint.
                cursor.execute("""INSERT OR IGNORE INTO guesses values (?, ?)""", (word, pickle.dumps(vec)))
            else:
                eliminated += 1
            if n % 100000 == 0:
                print(f"  pass 2: processed {n} (+1) lines")
                connection.commit()
    connection.commit()
    connection.close()
    valid_nearest_mat.flush()
    del valid_nearest_mat

    print("not added to db:", eliminated)
    print("valid nearest shape:", (len(valid_nearest_words), 300))

    # Save words separately and last — the docker entrypoint treats the
    # presence of this pickle as the "setup complete" marker.
    with open('data/valid_nearest_words.pkl', 'wb') as f:
        pickle.dump(valid_nearest_words, f)

    print("done")
