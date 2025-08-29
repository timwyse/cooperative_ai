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
OPENAI_API_KEY=your_openai_api_key
TOGETHER_API_KEY=your_together_api_key_api_key
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

 - Any old changes or commits in ```tims_branch``` that weren’t in main are now gone. Specifically ```reset --hard``` will overwrite local changes, so users should commit or stash any work they want to keep before running it. 
 
 <br>

3. If you have code that you want to persist through main branch updates but that aren't contributing to the core functionality of Colored Trails, you can include your own folder in main, eg ```Tim/```, where you can keep all your code. 

## Running experiments:
1. In ```main.py```, edit the ```CONFIG``` variable with the parameter values you want to use. You can refer to ```config.py``` to see which parameters are currently available for adjusting, as well as what are their default values. Available models are defined by the namedtuple '`Agent`' and exist in ```agents.py```. To add new models, include them in ```agents.py```.

2. Run
```bash
   python main.py
   ```

The game will display a grid using ```Pygame```, as well as a simple terminal interface. Human players can use the command line to take turns trading and moving resources.

## Sample Boards

Below are some examples of starting boards that can be created. These boards are located in the `starting_board_images` folder.

### Example 1: Mutual Cooperation Board
![Mutual Cooperation Board](starting_board_images/mutual_cooperation_board.png)

### Example 2: Prisoner's Dilemma Board
![Prisoner's Dilemma Board](starting_board_images/prisoners_dilemma_board.png)

### Example 3: Efficient Trade Board
![Efficient Trade Board](starting_board_images/efficient_trade_board.png)

You can create your own custom boards by modifying the `grid` parameter in the configuration .