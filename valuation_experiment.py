import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Button, Slider

# Define the function z(x; t, a, b)
def compute_z(x, t, a, b):
    return x * (1 + a * np.exp((b + 1j) * t * np.pi))

# Initialize parameters
x_init, t_init, a_init, b_init = 1.0, 1.5, 1.0, 0.0

# Set up figure and axes
fig, (ax_real, ax_complex) = plt.subplots(1, 2, figsize=(12, 5))
plt.subplots_adjust(bottom=0.25)

# Plot the real number axis
ax_real.axhline(0, color='black', linewidth=0.5)
ax_real.axvline(0, color='black', linewidth=0.5)
real_x_dot, = ax_real.plot(x_init, 0, 'bo', markersize=8, label="x")
real_z_dot, = ax_real.plot(0, 0, 'ro', markersize=8, label="z(x)")
ax_real.set_xlim(-2, 2)
ax_real.set_ylim(-1, 1)
ax_real.set_title("Real Number Axis")
ax_real.legend()

# Plot the complex plane
ax_complex.axhline(0, color='black', linewidth=0.5)
ax_complex.axvline(0, color='black', linewidth=0.5)
vertical_line, = ax_complex.plot([x_init, x_init], [-2, 2], 'b--', linewidth=1.5)
complex_z_dot, = ax_complex.plot(0, 0, 'ro', markersize=8, label="z(x)")
t = np.linspace(0, 2*np.pi, 300)
spiral = np.exp((0 + 1j) * t)  # Start with a unit circle
spiral_line, = ax_complex.plot(np.real(spiral), np.imag(spiral), 'gray', alpha=0.6)
ax_complex.set_xlim(-2, 2)
ax_complex.set_ylim(-2, 2)
ax_complex.set_title("Complex Plane")
ax_complex.legend()

# Add sliders
ax_x = plt.axes([0.2, 0.14, 0.65, 0.03])  # New slider position
ax_t = plt.axes([0.2, 0.1, 0.65, 0.03])
ax_a = plt.axes([0.2, 0.06, 0.65, 0.03])
ax_b = plt.axes([0.2, 0.02, 0.65, 0.03])

slider_x = Slider(ax_x, 'x', -2.0, 2.0, valinit=x_init)  # New slider
slider_t = Slider(ax_t, 't', 0.1, 3.0, valinit=t_init)
slider_a = Slider(ax_a, 'a', 0.0, 2.0, valinit=a_init)
slider_b = Slider(ax_b, 'b', -1.0, 1.0, valinit=b_init)

reset_ax = plt.axes([0.9, 0.02, 0.1, 0.04])  # Define position of the button
reset_button = Button(reset_ax, 'Reset')

def reset_sliders(event):
    slider_t.set_val(t_init)
    slider_a.set_val(a_init)
    slider_b.set_val(b_init)
    slider_x.set_val(x_init)

reset_button.on_clicked(reset_sliders)

# Update function
def update(val):
    x, t, a, b = slider_x.val, slider_t.val, slider_a.val, slider_b.val
    z_val = compute_z(x, t, a, b)

    vertical_line.set_xdata([x, x])

    # Update real number plot
    real_x_dot.set_data([x], [0])  # Update input x position
    real_z_dot.set_data([np.real(z_val)], [0])  # Ensure inputs are lists

    # Update complex plane
    complex_z_dot.set_data([np.real(z_val)], [np.imag(z_val)])  # Ensure inputs are lists

    # Update spiral path (avoid error by ensuring array input)
    r = np.linspace(0, 4*np.pi, 300)  # Extending rotation visualization
    spiral = np.exp((b + 1j) * t * np.pi * r)
    spiral_line.set_data(np.real(spiral), np.imag(spiral))

    fig.canvas.draw_idle()

# Connect slider updates
slider_x.on_changed(update)
slider_t.on_changed(update)
slider_a.on_changed(update)
slider_b.on_changed(update)

plt.show()
