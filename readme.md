### Docker Compose (recommended)

Runs everything — data download, processing, and gunicorn — in one container.
On first start the container downloads `cc.de.300.vec.gz` (~1.3GB) and the
German dictionary, then runs `process_vecs.py` to build `data/valid_guesses.db`
and `data/valid_nearest_mat.npy`. Expect ~5–10 minutes for the initial setup;
subsequent starts are instant because the processed artifacts live in a named
Docker volume.

```bash
docker compose up -d --build
```

Service is available at http://localhost:16430. Change the host port in
`docker-compose.yml` if you want a different one.

### Manual setup

create virtualenv:
```bash
python3.10 -m venv semantle-de
source semantle-de/bin/activate
```

install requirements
```bash
pip install -r requirements.txt
```

Download Word2Vec and dictionary data:
```bash
cd data
wget https://dl.fbaipublicfiles.com/fasttext/vectors-crawl/cc.de.300.vec.gz
gzip -d cc.de.300.vec.gz
wget https://www.winedt.org/dict/German.zip
unzip German.zip
```

save word2vec in db
```bash
cd ..
python process_vecs.py
```

(optional) Regenerate secrets
```bash
python generate_secrets.py
```

start flask/gunicorn (on ssh)
```bash
export FLASK_APP=semantle
nohup gunicorn semantle:app &
```

restart after pull
```bash
ps aux | grep gunicorn
kill -HUP <guniconr pid>
```

nginx...