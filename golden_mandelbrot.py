import numpy as np
import matplotlib.pyplot as plt

# Define the golden ratio
phi = (1 + np.sqrt(5)) / 2


def golden_mandelbrot(width=800, height=800, x_min=-2, x_max=2, y_min=-2, y_max=2, max_iter=100, escape_radius=10):
    """Computes the Golden Mandelbrot Set"""
    x = np.linspace(x_min, x_max, width)
    y = np.linspace(y_min, y_max, height)
    c = x[:, None] + 1j * y[None, :]
    z = np.zeros_like(c, dtype=np.complex128)
    escape_time = np.full(c.shape, max_iter, dtype=int)

    for n in range(max_iter):
        mask = np.abs(z) < escape_radius
        z[mask] = z[mask] ** phi + c[mask]
        escape_time[mask & (np.abs(z) >= escape_radius)] = n

    return escape_time


# Generate and display the Golden Mandelbrot Set
data = golden_mandelbrot()
plt.figure(figsize=(8, 8))
plt.imshow(data.T, extent=[-2, 2, -2, 2], cmap='magma', origin='lower')
plt.colorbar(label="Escape Time")
plt.title("Golden Mandelbrot Set")
plt.xlabel("Re(c)")
plt.ylabel("Im(c)")
plt.show()
