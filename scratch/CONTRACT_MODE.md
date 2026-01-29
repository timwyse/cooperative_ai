# Contract Mode in Colored Trails

The 'contract' version of the game introduces a mechanism for players to formalize agreements about resource exchanges and movement costs. This mode is designed to explore how contracts can improve cooperation and outcomes in scenarios where defection is possible.

## Key Features of "Strict" Contract Mode

1. **Contract Negotiation**:
   - Players can negotiate contracts during their turns.
   - Contracts specify resource exchanges or commitments to cover movement costs for **specific tiles**.

2. **Contract formalisation**:
   - A "judge" entity formalizes the contract based on the negotiation history.
   - The players then agree or disagree to this formal version created by the judgeg


3. **Contract Enforcement**:
   - Once agreed upon, contracts are enforced by the game system.
   - If a player lands on a specific tile that the other player agreed to pay for it, the game inforces this. No defection is possible


### Example Scenario

- **Player A** needs to move to a blue tile but lacks blue resources.
- **Player B** has surplus blue resources and agrees to cover the cost for Player A in exchange for red resources.
- A contract is negotiated and formalized:
  ```
  Player A will give 2 red resources to Player B.
  Player B will cover the cost of Player A's movement to the blue tile.
  ```
- The game enforces this contract, ensuring both players fulfill their commitments.


## How to Enable Contract Mode

1. Set the `contract` parameter in the game configuration to `True`.
2. Run the game as usual:
   ```bash
   python main.py
   ```
3. Players will have the option to negotiate contracts during their turns.

