import numpy as np
import matplotlib.pyplot as plt

# Number of samples
num_samples = 10_000

# Uniformly sample theta from [0, 2π]
theta = np.random.uniform(0, 2*np.pi, num_samples)
#theta_prime = np.random.uniform(0, 2*np.pi, num_samples)

# Compute x-components for a unit circle
x_circle = np.cos(theta)

# Parameters for the spiral (Archimedean)
a, b = 0.0, -0.5  # Initial radius and growth rate

theta = np.linspace(0, 4 * np.pi, 1000)  # Angle range
r = np.exp(-0.2 * theta)  # Converging inward spiral

x_spiral = r * np.cos(theta)

# Compute x-components for the spiral
#r_spiral = a + b * theta
#x_spiral = r_spiral * np.cos(theta)

# Plot histograms
fig, ax = plt.subplots(1, 2, figsize=(12, 5), sharey=True)

ax[0].hist(x_circle, bins=50, color='blue', alpha=0.7, density=True)
ax[0].set_title("X-Component Distribution (Circle)")
ax[0].set_xlabel("x")
ax[0].set_ylabel("Density")

ax[1].hist(x_spiral, bins=50, color='red', alpha=0.7, density=True)
ax[1].set_title("X-Component Distribution (Spiral)")
ax[1].set_xlabel("x")
ax[1].set_xlim(-3, 3)  # Set x-axis range for the spiral plot

plt.tight_layout()
plt.show()
