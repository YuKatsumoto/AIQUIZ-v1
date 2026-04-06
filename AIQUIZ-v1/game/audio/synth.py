import numpy as np
import pygame


def _create_sound_from_array(arr: np.ndarray) -> pygame.mixer.Sound:
    """Helper to convert a scaled numpy array into a Pygame Sound."""
    init_params = pygame.mixer.get_init()
    if not init_params:
        return None
        
    arr_16 = np.int16(arr * 32767.0)
    target_channels = init_params[2]
    
    # Repeat the array to match exactly the number of channels initialized by pygame
    if target_channels > 1:
        arr_final = np.column_stack([arr_16]*target_channels)
    else:
        arr_final = arr_16

    arr_final = np.ascontiguousarray(arr_final)
    
    try:
        return pygame.sndarray.make_sound(arr_final)
    except Exception as e:
        print(f"Warning: Failed to create sound: {e}")
        return None


def generate_correct_sound() -> pygame.mixer.Sound:
    """Generates a pleasant 'bling' or 'ding' arpeggio using Sine waves."""
    if not pygame.mixer.get_init():
        return None
    sample_rate = 44100
    duration = 0.4
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    
    # Frequencies: C5(523.25), E5(659.25), G5(783.99), C6(1046.50)
    # Give them a rapid arpeggio
    freq = 523.25
    envelope = np.exp(-t * 8.0)
    
    # We can do a quick frequency slide (sweep)
    f_sweep = np.linspace(600, 1200, len(t))
    wave = np.sin(2 * np.pi * f_sweep * t)
    
    # Add a little delay/echo chime layer
    f_sweep2 = np.linspace(800, 1600, len(t))
    wave2 = np.sin(2 * np.pi * f_sweep2 * t) * np.exp(-t * 6.0)
    
    combined = wave * envelope + wave2 * 0.5
    combined = np.clip(combined, -1.0, 1.0)
    
    return _create_sound_from_array(combined)


def generate_explosion_sound() -> pygame.mixer.Sound:
    """Generates a retro-style explosion using white noise with exponential decay."""
    if not pygame.mixer.get_init():
        return None
    sample_rate = 44100
    duration = 1.2
    
    noise = np.random.uniform(-1.0, 1.0, int(sample_rate * duration))
    t = np.linspace(0, duration, len(noise), False)
    
    # Exponential decay
    envelope = np.exp(-t * 4.0)
    
    # Apply a simple low-pass filter to give it a "bassy boom"
    # We can fake it by smoothing the noise array (convolution)
    window_length = 30
    window = np.ones(window_length) / window_length
    filtered = np.convolve(noise, window, mode='same')
    
    # Enhance the attack
    attack = np.ones_like(t)
    attack[:100] = np.linspace(0, 1, 100)
    
    boom = filtered * envelope * attack * 1.5
    boom = np.clip(boom, -1.0, 1.0)
    
    return _create_sound_from_array(boom)
