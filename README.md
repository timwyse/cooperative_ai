# cooperative_ai

This project is for exploring cooperative abilities of LM-agents, and exploring the impact that contracts can have on improving outcomes where cooperation is useful and defection is possible. It uses [Colored Trails](https://coloredtrails.atlassian.net/wiki/spaces/coloredtrailshome/overview) as a framework.

## Getting Started

1. Clone the repository:
```
   git clone https://github.com/timwyse/cooperative_ai.git
   ```
2. (Recommended) Create virtual environment
```bash
cd cooperative_ai
python -m venv .venv
source .venv/bin/activate
```
3. Install dependencies

```bash
   pip install -r requirements.txt
```

3. Create a .env file in the project root and include your API keys:
```
OPENAI_API_KEY=your_openai_api_key_here
```
### Recommended Version Control for Algoverse

1. Create your own branch if you want to run experiments without it affecting others.

eg. 
```bash
   git checkout -b tims_branch
```

<br>

2. As new features become available on main that you want to be able to use on your branch, run the following:
```bash
   git checkout tims_branch
   git fetch origin
   git reset --hard origin/main
```
Note that at this point:

 - ```tims_branch``` has exactly the same code as main on the remote.

 - Any old changes or commits in ```tims_branch``` that weren’t in main are now gone. Specifically ```reset --hard``` will overwrite local changes, so users should commit or stash their work before running it. 
 
 <br>

3. If you have code that you want to persist through main branch updates but that aren't contributing to the core functionality of Colored Trails, you can include your own folder in main, eg ```Tim/```, where you can keep all your code. 

## Running experiments:
1. In main.py, select the players and other parameters you want. The default configuration is for two human players: 
```python
DEFAULT_PLAYERS = [HUMAN, HUMAN]
```
Currently NANO, MINI, FOUR_1, FOUR_0 are also supported. You can see how they are configured in ```constants.py```

2. Run
```bash
   python main.py
   ```

The game will display a grid using ```Pygame```, and human players can use the command line to take turns trading and moving resources.
