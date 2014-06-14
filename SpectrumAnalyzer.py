#!/usr/bin/env python
import numpy
import time

MPD_FIFO = '/tmp/mpd.fifo'
SAMPLE_SIZE = 256
SAMPLING_RATE = 44100
FIRST_SELECTED_BIN = 5
NUMBER_OF_SELECTED_BINS = 10
SCALE_WIDTH = 20.0

def MoveCursorTo(new_x, new_y):
    'Move cursor to new_x, new_y'
    print '\033[' + str(new_x) + ';' + str(new_y) + 'H',
    
def DisplayConsole(spectrumValues):
    # Clear the console screen
    print '\033[2J',
    # Hide the console cursor
    print '\033[?25l',
    MoveCursorTo(0, 0)
    for val in spectrumValues:
        print "="*val
    time.sleep(0.05) 

class SpectrumAnalyzer(object):
    
    def __init__(self, sampleSize, samplingRate, firstSelectedBin, numberOfSelectedBins):
        self.sampleSize = sampleSize
        self.samplingRate = samplingRate
        self.firstSelectedBin = firstSelectedBin
        self.numberOfSelectedBins = numberOfSelectedBins
        
        # Initialization : frequency bins
        freq = numpy.fft.fftfreq(sampleSize) * samplingRate
        freqR = freq[:sampleSize/2]
        self.bins = freqR[firstSelectedBin:firstSelectedBin+numberOfSelectedBins]
        
        self.ResetSmoothing()
    
    def ResetSmoothing(self):
        self.count = 0
        self.average = 0
        
    def SmoothOut(self, x):
        self.count += 1
        self.average = (self.average*self.count + x) / (self.count+1)
        return self.average
    
    def ScaleList(self, list, scaleWidth):
        # Check NaN and +/-Inf are not present in the list
        list[numpy.isnan(spectrum)] = 0
        list[numpy.isinf(spectrum)] = 0
        
        # Compute a simple 'moving maximum'
        maximum = 2*self.SmoothOut(max(list))
        if maximum == 0:
            scaleFactor = 0.0
        else:
            scaleFactor = scaleWidth/float(maximum)
            
        # Compute the scaled list of values
        scaledList = [int(x*scaleFactor) for x in list]
        return scaledList
        
    def ComputeRMS(self, fifoFile, scaleWidth):
        # Read PCM samples from fifo
        rawSamples = fifoFile.read(self.sampleSize)    # will return empty lines (non-blocking)    
        pcm = numpy.fromstring(rawSamples, dtype=numpy.int16)
        
        # Normalize [-1; +1]
        pcm = pcm / (2.**15)
        
        # Compute RMS directly from signal
        rms = numpy.sqrt(numpy.mean(pcm**2))
        
        # Compute a simple 'moving maximum'
        maximum = 2*self.SmoothOut(rms)
        if maximum == 0:
            scaleFactor = 0.0
        else:
            scaleFactor = scaleWidth/float(maximum)
            
        return int(rms*scaleFactor)
        
    def ComputeSpectrum(self, fifoFile, scaleWidth):
        # Read PCM samples from fifo
        rawSamples = fifoFile.read(self.sampleSize)    # will return empty lines (non-blocking)    
        pcm = numpy.fromstring(rawSamples, dtype=numpy.int16)
        
        # Normalize [-1; +1]
        pcm = pcm / (2.**15)
        
        # Compute FFT
        N = pcm.size
        fft = numpy.fft.fft(pcm)
        uniquePts = numpy.ceil((N+1)/2.0)
        fft = fft[0:uniquePts]
        
        # Compute amplitude spectrum
        amplitudeSpectrum = numpy.abs(fft) / float(N)
        
        # Compute power spectrum
        p = amplitudeSpectrum**2
        
        # Multiply by two to keep same energy
        # See explanation:
        # https://web.archive.org/web/20120615002031/http://www.mathworks.com/support/tech-notes/1700/1702.html
        if N % 2 > 0: 
            # odd number of points
            # odd nfft excludes Nyquist point
            p[1:len(p)] = p[1:len(p)] * 2 
        else:
            # even number of points
            p[1:len(p) -1] = p[1:len(p) - 1] * 2
        
        # Power in logarithmic scale (dB)
        logPower = 10*numpy.log10(p)
        
        # Compute RMS from power
        #rms = numpy.sqrt(numpy.sum(p))
        #print "RMS(power):", rms
        
        # Select a significant range in the spectrum
        spectrum = logPower[self.firstSelectedBin:self.firstSelectedBin+self.numberOfSelectedBins]
            
        # Scale the spectrum 
        scaledSpectrum = self.ScaleList(spectrum, scaleWidth)
        
        return (self.bins, scaledSpectrum)
            
            
if __name__ == "__main__":
    analyzer = SpectrumAnalyzer(SAMPLE_SIZE, SAMPLING_RATE, FIRST_SELECTED_BIN, NUMBER_OF_SELECTED_BINS)
    with open(MPD_FIFO) as fifo:
        while True:
            (bins, scaledSpectrum) = analyzer.ComputeSpectrum(fifo, SCALE_WIDTH)
            DisplayConsole(scaledSpectrum)
    
    