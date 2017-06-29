import sys
import math
import wave
import struct
import pyaudio
import numpy as np
import matplotlib.pyplot as plt

# PyAudio object variable
pa = pyaudio.PyAudio()

# The mode the user chose with a script argument
MODE = sys.argv[1]
# The maximum size of an integer
MAX_INT = np.iinfo(np.int32).max
# Size of each read-in chunk
CHUNK = 1
# Amount of channels of the live recording
CHANNELS = 2
# Sample width of the live recording
WIDTH = 2
# Sample rate in Hz of the live recording
SAMPLE_RATE = 44100
# Set how often data for the result will be saved (every nth CHUNK)
if MODE != '-p' and MODE != '--playback':
    try:
        NTH_ITERATION = int(sys.argv[2])
    except (ValueError, IndexError):
        print('The second argument has to be a number')
        sys.exit()


def main():
    # Execute the chosen mode
    if MODE == '--file' or MODE == '-f':
        file_mode()
    elif MODE == '--live' or MODE == '-l':
        live_mode()
    elif MODE == '--playback' or MODE == '-p':
        playback_mode()
    else:
        print('Please either choose file-mode, live-mode or playback-mode with the first argument')


def file_mode():
    # Read in the given file
    (waveform, stream) = readin(sys.argv[3])

    # Give some feedback
    print('Now noise-cancelling the file')

    # Collecting the volume levels in decibels in a list
    decibel_levels = []

    # Counting the iterations of the while-loop
    iteration = 0

    # Read a first chunk and continue to do so for as long as there is a stream to read in
    original = waveform.readframes(CHUNK)
    while original != b'':
        try:
            # Invert the original audio
            inverted = invert(original)

            # Calculate the difference of the source and the inverted audio
            difference = calculate_difference(original, inverted)

            # Play back the audio stream of both on every second byte to preserve the original speed of the recording
            if iteration % 2 == 0:
                stream.write(original)
                stream.write(inverted)

            # On every nth iteration append the difference between the level of the source audio and the inverted one
            if iteration % NTH_ITERATION == 0:
                # Print the current difference
                print('Difference (in dB): {}'.format(difference))
                # Append the difference to the list used for the plot
                decibel_levels.append(difference)

            # Read in the next chunk of data
            original = waveform.readframes(CHUNK)

            # Add up one to the iterations
            iteration += 1
        except (KeyboardInterrupt, SystemExit):
            break

    # Stop the stream after there is no more data to read
    stream.stop_stream()
    stream.close()

    # Outputting feedback regarding the end of the file
    print('Finished noise-cancelling the file')

    # Plot the results
    plot_results(decibel_levels, NTH_ITERATION)

    # Terminate PyAudio as well as the program
    pa.terminate()
    sys.exit()


def live_mode():
    # Start live recording
    print('Now noise-cancelling live')

    # Create a new PyAudio object using the preset constants
    stream = pa.open(
        format=pa.get_format_from_width(WIDTH),
        channels=CHANNELS,
        rate=SAMPLE_RATE,
        frames_per_buffer=CHUNK,
        input=True,
        output=True
    )

    # Collecting the volume levels in decibels in a list
    decibel_levels = []

    # Grab a chunk of data in iterations according to the preset constants
    try:
        for i in range(0, int(SAMPLE_RATE / CHUNK * sys.maxunicode)):
            # Read in a chunk of live audio on each iteration
            original = stream.read(CHUNK)

            # Invert the original audio
            inverted = invert(original)

            # Calculate the difference of the source and the inverted audio
            difference = calculate_difference(original, inverted)

            # Play back the inverted audio
            stream.write(inverted, CHUNK)

            # On every nth iteration append the difference between the level of the source audio and the inverted one
            if i % NTH_ITERATION == 0:
                # Print the current difference
                print('Difference (in dB): {}'.format(difference))
                # Append the difference to the list used for the plot
                decibel_levels.append(difference)
    except (KeyboardInterrupt, SystemExit):
        # Outputting feedback regarding the end of the file
        print('Finished noise-cancelling the file')

        # Plot the results
        plot_results(decibel_levels, NTH_ITERATION)

        # Terminate the program
        stream.stop_stream()
        stream.close()
        pa.terminate()
        sys.exit()


def playback_mode():
    # Read in the given file
    (waveform, stream) = readin(sys.argv[2])

    # Give some feedback
    print('Now playing back the file')

    # Read a first chunk and continue to do so for as long as there is a stream to read in
    original = waveform.readframes(CHUNK)
    while original != b'':
        try:
            # Play back the audio
            stream.write(original)

            # Read in the next chunk of data
            original = waveform.readframes(CHUNK)
        except (KeyboardInterrupt, SystemExit):
            break

    # Stop the stream after there is no more data to read
    stream.stop_stream()
    stream.close()

    # Outputting feedback regarding the end of the file
    print('Finished playing back the file')

    # Terminate PyAudio as well as the program
    pa.terminate()
    sys.exit()


def readin(file):
    """
    Reads in the given wave file and returns a new PyAudio stream object from it.

    :param file: The path to the file to read in
    :return (waveform, stream): (The actual audio data as a waveform, the PyAudio object for said data)
    """

    # Open the waveform from the command argument
    try:
        waveform = wave.open(file, 'r')
    except wave.Error:
        print('The program can only process wave audio files (.wav)')
        sys.exit()
    except FileNotFoundError:
        print('The chosen file does not exist')
        sys.exit()

    # Load PyAudio and create a useable waveform object
    stream = pa.open(
        format=pa.get_format_from_width(waveform.getsampwidth()),
        channels=waveform.getnchannels(),
        rate=waveform.getframerate(),
        output=True
    )

    # Return the waveform as well as the generated PyAudio stream object
    return waveform, stream


def invert(data):
    """
    Inverts the byte data it received utilizing an XOR operation.

    :param data: A chunk of byte data
    :return inverted: The same size of chunked data inverted bitwise
    """

    # Convert the bytestring into an integer
    intwave = int.from_bytes(data, byteorder='big')
    # Invert the integer
    intwave ^= MAX_INT
    # Convert the integer back into a bytestring
    inverted = intwave.to_bytes(4, byteorder='big')
    # Return the inverted audio data
    return inverted


def calculate_decibel(data):
    """
    Calculates the volume level in decibel of the given data

    :param data: A bytestring used to calculate the decibel level
    :return db: The calculated volume level in decibel
    """

    count = len(data) / 2
    form = "%dh" % count
    shorts = struct.unpack(form, data)
    sum_squares = 0.0
    for sample in shorts:
        n = sample * (1.0 / 32768)
        sum_squares += n * n
    rms = math.sqrt(sum_squares / count) + 0.0001
    db = 20 * math.log10(rms)
    return db


def calculate_difference(data_1, data_2):
    """
    Calculates the difference level in decibel between the received binary inputs

    :param data_1: The first binary digit
    :param data_2: The second binary digit
    :return difference: The calculated difference level (in dB)
    """

    difference = calculate_decibel(data_1) - calculate_decibel(data_2)
    return difference


def plot_results(data, nth_iteration):
    """
    Plots the list it receives and cuts off the first ten entries to circumvent the plotting of initial silence

    :param data: A list of data to be plotted
    :param nth_iteration: Used for the label of the x axis
    """

    # Plot the data
    plt.plot(data[10:])

    # Label the axes
    plt.xlabel('Time (every {}th {} byte)'.format(nth_iteration, CHUNK))
    plt.ylabel('Volume level difference (in dB)')

    # Calculate and output the absolute median difference level
    plt.suptitle('Difference - Median (in dB): {}'.format(np.round(np.fabs(np.median(data)), decimals=5)), fontsize=14)

    # Display the plotted graph
    plt.show()


main()
