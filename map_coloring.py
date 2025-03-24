import numpy as np
import dimod
from qdeepsdk import QDeepHybridSolver
from utilities import visualize_map

# Define a Province class with color variables.
class Province:
    def __init__(self, name):
        self.name = name
        self.red = name + "_r"
        self.green = name + "_g"
        self.blue = name + "_b"
        self.yellow = name + "_y"

# Set up provinces.
bc = Province("bc")   # British Columbia
ab = Province("ab")   # Alberta
sk = Province("sk")   # Saskatchewan
mb = Province("mb")   # Manitoba
on = Province("on")   # Ontario
qc = Province("qc")   # Quebec
nl = Province("nl")   # Newfoundland and Labrador
nb = Province("nb")   # New Brunswick
pe = Province("pe")   # Prince Edward Island
ns = Province("ns")   # Nova Scotia
yt = Province("yt")   # Yukon
nt = Province("nt")   # Northwest Territories
nu = Province("nu")   # Nunavut

provinces = [bc, ab, sk, mb, on, qc, nl, nb, pe, ns, yt, nt, nu]

# Define province neighbours (i.e. provinces sharing a border).
neighbours = [(bc, ab),
              (bc, nt),
              (bc, yt),
              (ab, sk),
              (ab, nt),
              (sk, mb),
              (sk, nt),
              (mb, on),
              (mb, nu),
              (on, qc),
              (qc, nb),
              (qc, nl),
              (nb, ns),
              (yt, nt),
              (nt, nu)]

# Parameters for the one-hot constraint.
# We use a penalty term lambda*(sum(x) - 1)^2.
lambda_onehot = 1.0  # penalty strength for one-hot constraint

# Parameter for neighbour conflict: if two neighbouring provinces share the same color.
lambda_neighbour = 2.0

# Build a BQM manually.
bqm = dimod.BinaryQuadraticModel({}, {}, 0.0, dimod.BINARY)

# For each province, add the one-hot constraint.
# For province p with variables: p.red, p.green, p.blue, p.yellow:
#   The penalty is lambda * (x_r + x_g + x_b + x_y - 1)^2.
# Expansion yields:
#   lambda * [ (x_r+x_g+x_b+x_y) + 2*sum_{i<j} x_i*x_j - 2*(x_r+x_g+x_b+x_y) + 1 ]
#   = -lambda*(x_r+x_g+x_b+x_y) + 2*lambda*(sum_{i<j} x_i*x_j) + constant.
for p in provinces:
    colors = [p.red, p.green, p.blue, p.yellow]
    # Add linear terms: for each color variable, add -lambda_onehot.
    for var in colors:
        # If the variable already exists, add to its bias.
        bqm.add_variable(var, -lambda_onehot)
    # Add quadratic terms for each pair of colors in the same province.
    for i in range(len(colors)):
        for j in range(i+1, len(colors)):
            bqm.add_interaction(colors[i], colors[j], 2 * lambda_onehot)
    # (We ignore constant offset, as it does not affect the optimal solution.)

# For each pair of neighbouring provinces, add a penalty if they share the same color.
for p, q in neighbours:
    for color in ['_r', '_g', '_b', '_y']:
        var_p = p.name + color
        var_q = q.name + color
        bqm.add_interaction(var_p, var_q, lambda_neighbour)

# At this point, bqm encodes all our constraints.
# Convert the BQM to a QUBO dictionary and get an offset.
qubo, offset = bqm.to_qubo()

# Create a mapping from variable names to indices for constructing a NumPy matrix.
variables = list(bqm.variables)
mapping = {var: i for i, var in enumerate(variables)}
n = len(variables)
matrix = np.zeros((n, n))
for (var_i, var_j), coeff in qubo.items():
    i = mapping[var_i]
    j = mapping[var_j]
    matrix[i, j] = coeff

# Initialize QDeepHybridSolver and set the authentication token.
solver = QDeepHybridSolver()
solver.token = "your-auth-token-here"  # Replace with your valid token

# Solve the QUBO by passing the NumPy array.
result = solver.solve(matrix)
# The result is expected to be a dictionary with a 'sample' key mapping indices to binary values.
raw_solution = result['sample']

# Map the solution back to the original variable names.
solution = {variables[i]: raw_solution.get(i, 0) for i in range(n)}

print("Solution:", solution)

# Verify the solution manually.
# For each province, check that exactly one color is selected.
def verify_solution(solution, provinces):
    valid = True
    for p in provinces:
        colors = [solution.get(p.red, 0), solution.get(p.green, 0),
                  solution.get(p.blue, 0), solution.get(p.yellow, 0)]
        if sum(colors) != 1:
            print(f"Province {p.name} has an invalid assignment: {colors}")
            valid = False
    # For each pair of neighbours, check that they do not share the same color.
    for p, q in neighbours:
        for color in ['_r', '_g', '_b', '_y']:
            if solution.get(p.name + color, 0) == 1 and solution.get(q.name + color, 0) == 1:
                print(f"Neighbouring provinces {p.name} and {q.name} share the same color {color}")
                valid = False
    return valid

is_valid = verify_solution(solution, provinces)
print("Does solution satisfy our constraints?", is_valid)

# Visualize the solution.
# Hard-code node positions reminiscent of the map of Canada.
node_positions = {"bc": (0, 1),
                  "ab": (2, 1),
                  "sk": (4, 1),
                  "mb": (6, 1),
                  "on": (8, 1),
                  "qc": (10, 1),
                  "nb": (10, 0),
                  "ns": (12, 0),
                  "pe": (12, 1),
                  "nl": (12, 2),
                  "yt": (0, 3),
                  "nt": (2, 3),
                  "nu": (6, 3)}

# For visualization, we need to determine the color for each province.
# We use the variable with value 1 among {p.red, p.green, p.blue, p.yellow}.
def get_province_color(p, solution):
    if solution.get(p.red, 0) == 1:
        return "red"
    elif solution.get(p.green, 0) == 1:
        return "green"
    elif solution.get(p.blue, 0) == 1:
        return "blue"
    elif solution.get(p.yellow, 0) == 1:
        return "yellow"
    else:
        return "gray"

# Build a dictionary of colors for each province.
province_colors = {p.name: get_province_color(p, solution) for p in provinces}

# Prepare nodes and edges for visualization.
nodes = [p.name for p in provinces]
edges = [(p.name, q.name) for p, q in neighbours]

# Visualize the map using the provided visualize_map function.
visualize_map(nodes, edges, solution, node_positions=node_positions, node_colors=province_colors)
