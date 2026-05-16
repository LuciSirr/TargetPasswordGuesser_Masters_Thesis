# Profile-Based Password Generator

This master thesis implements a tool for generating password candidates from a target
profile. It trains a structural password model from profile data and previous
password examples, then uses that model to generate a wordlist for a specific
profile.

The generator can also expand profile information before generation. For
example, it can add first-name variants, region variants, and semantically
related interests using DBpedia and embedding models.

Use this tool only for authorized research, evaluation, or security testing.

## Workflow

1. Create training profiles and configure the system.
2. Train a model on a set of profiles, or use a pretrained model from
   `models/pcfg`.
3. Generate a password wordlist for a specific profile.

## Environment Setup

Requirements:

- Python 3
- pip
- local project files in `models`, `resources`, `configs`, and `data`

Create and activate a virtual environment in the project root:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install dependencies:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

The main dependencies are:

- `numpy`
- `PyYAML`
- `requests`
- `nicknames`
- `wikipedia2vec`
- `fasttext-wheel`

## Additional Resources

The project uses language-specific Wikipedia2Vec and FastText models configured
in `configs/resources.yaml`.

Example embedding files:

- `models/embeddings/enwiki_20180420_100d.pkl`
- `models/embeddings/dewiki_20180420_100d.pkl`
- `models/embeddings/cc.en.300.bin`
- `models/embeddings/cc.de.300.bin`
- `models/embeddings/cc.cs.300.bin`

Wikipedia2Vec models are available from:

```text
https://wikipedia2vec.github.io/wikipedia2vec/pretrained/
```

FastText crawl vectors are available from:

```text
https://fasttext.cc/docs/en/crawl-vectors.html
```

The configured embedding models can also be downloaded automatically:

```bash
python -m scripts.setup_embeddings
```

To download only selected languages:

```bash
python -m scripts.setup_embeddings --languages en de
```

Approximate storage requirements:

- English: about 11 GB
- Czech: about 8 GB
- German: about 11 GB

When using semantic profile enhancement with `-e`, at least 8 GB of RAM is
recommended.

For Czech name diminutives, the project uses the JSON file configured under
`name_diminutives` in `configs/resources.yaml`.

When DBpedia-based expansion is enabled, the tool needs access to the configured
SPARQL endpoint. By default this is:

```text
https://dbpedia.org/sparql
```

For offline usage, configure a local endpoint in `configs/resources.yaml`, for
example:

```yaml
dbpedia_sparql_url: http://localhost:8890/sparql
```

## Profile GUI

A local web GUI is available for creating profile JSON files and editing
configuration files:

```bash
python -m scripts.gui
```

After starting the GUI, open:

```text
http://127.0.0.1:8765
```

The GUI supports:

- creating and saving profile files in JSON format
- editing `configs/runtime.yaml`
- editing `configs/resources.yaml`
- previewing generated profile and configuration content

## Train a Model

Train a PCFG model from a directory of profile JSON files:

```bash
python -m scripts.train_model \
  --profiles_dir <training_profiles> \
  --output_model <output_model> \
  -l <language>
```

Arguments:

- `--profiles_dir`: directory containing training profiles
- `--output_model`: output model file path
- `-l`, `--language`: one of `en`, `cz`, or `de`
- `--runtime_config`: optional runtime configuration path, defaults to
  `configs/runtime.yaml`
- `--run_log [PATH]`: optionally write a JSON run log with arguments, runtime
  configuration, effective settings, and seed information. If `PATH` is omitted,
  a timestamped file is written under `logs/`.

Example for English profiles:

```bash
python -m scripts.train_model \
  --profiles_dir data/uk/test \
  --output_model pcfg_model_en.json \
  -l en
```

Example for Czech profiles:

```bash
python -m scripts.train_model \
  --profiles_dir data/cz/test \
  --output_model pcfg_model_cz.json \
  -l cz
```

## Generate Passwords

Generate password candidates from a trained model and profile:

```bash
python -m scripts.generate_passwords \
  -g <model> \
  -p <profile> \
  -n <num_passwords> \
  -l <language>
```

Arguments:

- `-g`, `--grammar`: path to the trained PCFG model
- `-p`, `--profile`: path to the target profile JSON file
- `-n`, `--num-passwords`: number of passwords to generate, defaults to `20`
- `-e`, `--enhance-profile`: enable semantic profile expansion
- `-l`, `--language`: one of `en`, `cz`, or `de`
- `--runtime_config`: optional runtime configuration path, defaults to
  `configs/runtime.yaml`
- `--seed`: seed for reproducible random-mode generation. If omitted, the value
  from `generation.seed` in the runtime configuration is used.
- `--run_log [PATH]`: optionally write a JSON run log with arguments, runtime
  configuration, effective settings, and the seed used. During generation, the
  log path is printed to stderr so stdout remains reserved for passwords.
- `-v`, `--verbose`: print progress messages during enhancement and generation

Example:

```bash
python -m scripts.generate_passwords \
  -g models/pcfg/pcfg_model_cz.json \
  -l cz \
  -n 1000 \
  -p data/Radek_Vesely.json
```

Example with semantic profile enhancement and a run log:

```bash
python -m scripts.generate_passwords \
  -g models/pcfg/pcfg_model_cz.json \
  -p data/Radek_Vesely.json \
  -n 1000 \
  -l cz \
  -e \
  --run_log
```

## Profile JSON Format

A profile is a JSON object describing the target person. Supported fields include:

- `self_first_name`
- `self_last_name`
- `partner_first_name`
- `partner_last_name`
- `birth_date`
- `age`
- `region`
- `nationality`
- `company`
- `car_brand`
- `interests`
- `previous_passwords`
- `children`
- `pets`

Training profiles should include `previous_passwords`, because those passwords
are used to learn the structural model.

## Runtime Configuration

The file `configs/runtime.yaml` controls training, generation, and token
enhancement.

### Model Training

```yaml
model_training:
  max_password_length: 25
  embedding_fallback_threshold: 0.2
```

- `max_password_length`: maximum password length considered during training.
  Longer passwords are skipped to avoid bias from extreme cases.
- `embedding_fallback_threshold`: minimum similarity required when token
  categorization falls back to embedding similarity.

### Password Generation

```yaml
generation:
  mode: deterministic
  unique: true
  seed: null
```

- `mode`: `deterministic` or `random`
- `deterministic`: generate the most probable combinations according to the model
- `random`: sample passwords based on model probabilities
- `unique`: avoid duplicate generated passwords
- `seed`: optional seed for reproducible random generation

### Token Enhancement

```yaml
token_enhancement:
  dbpedia:
    graph_depth: 1
    graph_width: 5
    threshold_dbp: 0.3
    category_weight: 0.7
    type_weight: 0.3
    request_timeout: 30
    request_delay: 0.1

  embeddings:
    threshold_w2v: 0.4
    threshold_fasttext: 0.35

  max_expansion: 5
```

DBpedia settings:

- `graph_depth`: DBpedia graph traversal depth
- `graph_width`: maximum number of outgoing relations explored per node
- `threshold_dbp`: minimum DBpedia score for accepted candidates
- `category_weight`: category similarity weight
- `type_weight`: type similarity weight
- `request_timeout`: maximum SPARQL response wait time in seconds
- `request_delay`: delay between DBpedia requests

Embedding settings:

- `threshold_w2v`: minimum Wiki2Vec similarity threshold
- `threshold_fasttext`: minimum FastText fallback similarity threshold
- `max_expansion`: maximum number of expansions added per input token

## Resources Configuration

External resources are configured in `configs/resources.yaml`.

Example structure:

```yaml
dbpedia_sparql_url: https://dbpedia.org/sparql
languages:
  en:
    w2v_model: models/embeddings/enwiki_20180420_100d.pkl
    fasttext_model: models/embeddings/cc.en.300.bin

  cz:
    fasttext_model: models/embeddings/cc.cs.300.bin
    name_diminutives: resources/czech_name_diminutives.json

  de:
    w2v_model: models/embeddings/dewiki_20180420_100d.pkl
    fasttext_model: models/embeddings/cc.de.300.bin
```

Fields:

- `dbpedia_sparql_url`: DBpedia SPARQL endpoint
- `w2v_model`: path to the Wikipedia2Vec embedding model
- `fasttext_model`: path to the FastText embedding model
- `name_diminutives`: optional Czech diminutives dictionary

## Maintenance

Remove Python cache files:

```bash
make clean-pycache
```

or:

```bash
make clean
```
