# AutoReach CLI

## Install
```
pip install -e .  # from repo root (uses setup_cli.py)
```
or once published:
```
pip install autoreach-cli
```

## Usage
```
autoreach config                          # set API keys (first-time setup)
autoreach find --city Athens --type restaurants
autoreach scrape                          # scrape emails from websites
autoreach send                            # preview & send interactively
autoreach send --language greek           # send in Greek
autoreach send --auto                     # batch mode, no prompts
autoreach leads                           # list all leads
autoreach stats                           # analytics
autoreach export --output my_leads.csv    # export to CSV
```

## Config stored at
`~/.autoreach/autoreach.db` (SQLite)
