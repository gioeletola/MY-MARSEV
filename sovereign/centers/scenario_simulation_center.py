"""ScenarioSimulation Center — scenario planning & simulation."""
from sovereign.centers.simple_center import SimpleCenter

class ScenarioSimulationCenter(SimpleCenter):
    CENTER_ID = 'scenario_simulation_centre'
    DESCRIPTION = 'Scenario Planning & Simulation'
    PRIMARY_MODE = 'command'
    AGENTS = ['scenario_simulator', 'scenario_finance', 'future_scenario', 'financial_risk']
    DOMAIN_MAP = {'scenario': 'scenario_simulator', 'simulation': 'scenario_simulator', 'finance scenario': 'scenario_finance', 'future': 'future_scenario', 'risk': 'financial_risk'}
    DEFAULT_AGENT = 'scenario_simulator'

center = ScenarioSimulationCenter()
