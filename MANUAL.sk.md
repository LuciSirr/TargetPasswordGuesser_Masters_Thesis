
# Manuál k projektu Target Password Guesser
## Účel projektu

Projekt je zameraný na:

- trénovanie jednoduchého modelu reprezentujúceho štruktúru hesiel na základe profilových dát,
- generovanie slovníka hesiel pre konkrétnu cieľovú osobu,
- voliteľné rozšírenie profilu o odvodené tokeny (napr. mená, varianty regiónov alebo záujmy získané z DBpedia).

Inými slovami, zo zbierky používateľských profilov sa naučí model typických vzorov hesiel, ktorý následne umožňuje generovať slovník pre konkrétny profil. Natrénované modely sú dostupné v zložke `\models\pcfg`

## Typický postup práce

1. Vytvoriť alebo upraviť profil a konfiguráciu nástroja.
2. Natrénovať model na sade profilov (Prípadne zvoliť predtrénovaný model v zložke `\models\pcfg`).
3. Vygenerovať slovník hesiel pre konkrétny profil.

## Príprava prostredia

Stiahnutie modelov vyžaduje nasledovné množstvo uložného priestoru:
	- Anglický jazyk: ~11GB
	- Český jazyk: ~8GB
	- Nemecký jazyk: ~11GB

Pre spustenie skriptov na trénovanie a generovanie hesiel v režime rozšírenia profilu (prepínač -e) je nutné mať dostupných aspoň 8GB RAM.

Pred prvým spustením je potrebné mať nainštalovaný:

- Python 3
- `pip`
- lokálne súbory modelov a zdrojov, ktoré projekt používa v zložkách `models`, `resources`, `configs` a `data`

Odporúčaný postup je použiť virtuálne prostredie `venv`.

Vytvorenie virtuálneho prostredia v koreňovom adresári projektu:

```bash
python3 -m venv .venv
```

Aktivácia prostredia

```bash
source .venv/bin/activate
```

Následne nainštalujte potrebné balíčky:

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

Súbor `requirements.txt` obsahuje balíčky používané hlavnými skriptmi projektu, konkrétne:

- `numpy`
- `PyYAML`
- `requests`
- `nicknames`
- `wikipedia2vec`
- `fasttext-wheel`

Pre korektné fungovanie projektu je ďalej potrebné:

- mať dostupné embedding Wikipedia2vec a fastext modely uvedené v `configs/resources.yaml`, napríklad 
Wikipedia2vec: `models/embeddings/enwiki_20180420_100d.pkl`, `models/embeddings/dewiki_20180420_100d.pkl` (dostupné na https://wikipedia2vec.github.io/wikipedia2vec/pretrained/) 

FastText: `models/embeddings/cc.cs.300.bin` (dostupné na https://fasttext.cc/docs/en/crawl-vectors.html)
- mať dostupný súbor `resources/czech_name_diminutives.json` pre české zdrobneniny
- pri použití DBpedia rozširovania mať prístup na internet k endpointu `https://dbpedia.org/sparql`, alebo si nastaviť vlastný lokálny endpoint v `configs/resources.yaml`

Modely uvedené v `configs/resources.yaml` je možné stiahnuť automaticky:

```bash
python -m scripts.setup_embeddings
```

Voliteľne je možné obmedziť sťahovanie len na vybrané jazyky:

```bash
python -m scripts.setup_embeddings --languages en de
```

Overenie, že sa používa správne virtuálne prostredie:

```bash
which python
python --version
```

Po aktivácii `venv` je možné spúšťať GUI, trénovanie aj generovanie hesiel príkazmi uvedenými nižšie.

  ## 1. Tvorba profilu a konfigurácie
Na vytváranie profilov slúži jednoduché webové GUI.
Spustenie:

```bash
python -m scripts.profile_gui
```  

Po spustení je GUI dostupné v prehliadači na adrese:
http://127.0.0.1:8765
GUI umožňuje:
- vytvárať a ukladať profily v JSON formáte,
- upravovať súbory `runtime.yaml` a `resources.yaml`,
- priebežne zobrazovať náhľad výsledného obsahu.

## 2. Trénovanie modelu
```bash

python  scripts/train_model.py  --profiles_dir  <profily_na_trening>  --output_model  <vysledny_model>  -l  <jazyk_trenovacich_profilov>

```
Argumenty:
-  `--profiles_dir`: adresár s profilmi určenými na tréning modelu

-  `--output_model`: názov súboru pre vytvorený model

-  `-l`, `--language`: jedna z hodnôt `en`, `cz`, `de`

-  `--runtime_config`: volitelná cesta ku konfiguracii, predvolené `configs/runtime.yaml`

-  `--run_log [PATH]`: volitelne vytvori JSON log behu s argumentmi, runtime konfiguraciou,
   efektivnymi nastaveniami a semienkom. Ak sa `PATH` neuvedie, subor sa ulozi do `logs/`
   s casovou peciatkou.

  Príklad spustenia pre anglické profily:
```bash

python -m scripts.train_model  --profiles_dir  data/uk/test  --output_model  pcfg_model_uk.json  -l  en

```
  Príklad spustenia pre české profily:
```bash

python -m scripts.train_model  --profiles_dir  data/cz/test  --output_model  pcfg_model_cz.json  -l  cz

```
 
 
## 3. Generovanie hesiel


```bash

python  -m  scripts.generate_passwords  -g  <model>  -p  <profil>  -n  <počet_hesiel>  -l  <jazyk>

```
  Príklad spustenia pre testovací profil `Radek_Vesely.json`:
  ```bash
  
  python3 -m scripts.generate_passwords -g models/pcfg/pcfg_model_cz.json -l cz -n 1000 -p data/Radek_Vesely.json 
  
  ```

Argumenty:
-  `-g`, `--grammar`: cesta k natrénovanému PCFG modelu

-  `-p`, `--profile`: cesta k profilu 

-  `-n`, `--num-passwords`: počet hesiel ktoré nástroj vygeneruje, predvolene `20`

-  `-e`, `--enhance-profile`: zapne semantické rozšírenie profilu

-  `-l`, `--language`: jedna z hodnôt `en`, `cz`, `de`

-  `--runtime_config`: volitelna cesta ku konfiguracii, predvolene `configs/runtime.yaml`

-  `--seed`: semienko pre reprodukovatelne generovanie v nahodnom rezime. Ak sa neuvedie,
   pouzije sa hodnota `generation.seed` z runtime konfiguracie.

-  `--run_log [PATH]`: volitelne vytvori JSON log behu s argumentami, runtime konfiguraciou,
    nastaveniami a pouzitym semienkom. Pri generovani hesiel sa cesta k logu
   vypise na stderr, aby stdout ostal len pre hesla. Ak sa `PATH` neuvedie, subor sa ulozi
   do `logs/` s casovou peciatkou.

-  `-v`, `--verbose`: aktivuje logovanie počas behu programu

## Vstupne subory
### Profil v JSON
Profil je JSON objekt popisujúci cielovú osobu. Obsahuje nasledovné atribúty:
```bash
self_first_name
self_last_name
partner_first_name
partner_last_name
birth_date
age
region
nationality
company
car_brand
interests
previous_passwords
children
pets
```
Vstupné `.json` súbory určené pre konfiguráciu sú modifikovatelné prostredníctvom GUI. Dopredu nakonfigurované súbory sú dostupné v zložke `configs`

### Runtime konfigurácia  
  
Súbor `configs/runtime.yaml` určuje správanie systému počas trénovania aj generovania.  
Konfigurovatelné atribúty a ich význam:

```bash
- Táto sekcia ovplyvňuje učenie modelu z profilových dát.
model_training:
	max_password_length: 25
	
	- Určuje maximálnu dĺžku hesla,
	s ktorou sa pri trénovaní pracuje. Dlhšie heslá môžu byť ignorované alebo odfiltrované, 
	aby model nebol zbytočne ovplyvnený extrémne dlhými prípadmi.
	
	embedding_fallback_threshold: 0.2

	- Tento parameter sa používa pri kategorizácii tokenov počas trénovania.
	Ak sa token nepodarí jednoznačne zaradiť pravidlami, môže sa použiť embeddingový 
	model ako fallback. Hodnota určuje minimálnu podobnosť, od ktorej sa ešte výsledok
	považuje za prijateľný.
	
- Táto sekcia riadi spôsob generovania kandidátov hesiel.
generation:
	mode: deterministic/random
	
  - Určuje režim generovania.
  - deterministic - systém generuje deterministicky najpravdepodobnejšie kombinácie podľa modelu
  - random - systém generuje heslá podľa pravdepodobností z modelu.

  unique: true 

  - Generované heslá sú unikátne, teda bez duplicít

  seed: null

  - Volitelne semienko pre reprodukovatelne generovanie v rezime random.

- Táto sekcia riadi rozširovanie profilových údajov pred samotným generovaním hesiel.
  Ide napríklad o rozšírenie mien, regiónov alebo záujmov.
token_enhancement:
	- Nastavenia pre rozširovanie pomocou DBpedie.
	dbpedia:
		graph_depth: 1
		
		- Hĺbka prechádzania DBpedia grafu. Hodnota  1  znamená, že sa systém pozrie len
		na priamo susediace entity od počiatočného uzla.
		
		graph_width: 5

		- Maximálny počet odchádzajúcich vzťahov, ktoré sa z jedného uzla budú skúmať. 
		Obmedzuje veľkosť prehľadávania.
	  
		threshold_dbp: 0.3 

        - Minimálny DBpedia skórovací prah. Ak má kandidát nižšie skóre, nebude použitý ako
		rozšírenie.

		category_weight: 0.7 - Váha zhody kategórií pri výpočte DBpedia skóre.
		
		type_weight: 0.3 - Váha zhody typov pri výpočte DBpedia skóre.
		
		request_timeout: 30 - Maximálny čas v sekundách, ktorý bude systém čakať na
		odpoveď SPARQL endpointu.
		
		request_delay: 0.1 - Pauza medzi požiadavkami na DBpedia endpoint v sekundách.
		Slúži na  obmedzenie tempa dotazov.

  Nastavenia pre embeddingové modely.
	embeddings:

		threshold_w2v: 0.4
		
		- Minimálna podobnosť pre Wiki2Vec. Ak je podobnosť kandidáta nižšia,
		nebude akceptovaný.
		
		threshold_fasttext: 0.35
		
		- Minimálna podobnosť pre FastText fallback. Ak FastText vráti nižšie skóre, 
		kandidát sa zahodí.

		max_expansion: 5
		
		- Určuje maximálny počet rozšírení, ktoré sa pre jeden vstupný token pridajú. 
		Napríklad pre jeden záujem alebo meno sa pridá najviac 5 nových variantov.
```


### Resources konfigurácia  

Konfigurácia externých zdrojov, ktoré projekt používa. Súbor je definovaný v `\conigs\resources.yaml`
```bash
- Adresa SPARQL endpointu pre DBpediu.
Používa sa pri rozširovaní profilu, keď systém hľadá súvisiace entity,
kategórie alebo typy cez DBpedia.
dbpedia_sparql_url: https://dbpedia.org/sparql
- Pre offline DBpediu je možné použiť
dbpedia_sparql_url: http://localhost:8890/sparql
```
Návod na konfiguráciu offline DBpedie: https://github.com/dbpedia/virtuoso-sparql-endpoint-quickstart
```bash
- Táto sekcia obsahuje jazykovo špecifické zdroje.
  Pre každý jazyk je možné nastaviť:
languages:
	w2v_model: models/embeddings/enwiki_20180420_100d.pkl
	- cesta k Wiki2Vec modelu
	
	fasttext_model: models/embeddings/cc.en.300.bin
	- cesta k FastText modelu
	
	- Nastavenie špecifické pre český jazyk:
	name_diminutives: data/resources/czech_name_diminutives.json

	- Slovník s modifikáciami českých mien
```
