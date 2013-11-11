import cv2
import math
import numpy
import subprocess
import os

import colors
import geometry as g
import text
from dimension import Dimension
from stopwatch import Stopwatch
import numpy

stopwatch = Stopwatch()

class Page:

    def __init__(self, path, showSteps=False):

        stopwatch.reset(path)

        self.showSteps = showSteps
        greyscaleImage = cv2.imread(path, cv2.CV_LOAD_IMAGE_GRAYSCALE)
        colorImage = cv2.imread(path, cv2.CV_LOAD_IMAGE_COLOR)

        if False:
            self.display(colorImage)

        self.characters = text.CharacterSet(greyscaleImage)
        self.words = self.characters.getWords()

        self.image = colorImage

        stopwatch.lap("finished analysing page")
        stopwatch.endRun()
        
    
    def paint(self, image):

        print len(self.words)
        for word in self.words:
            image = word.paint(image, colors.RED)

        return image

    def save(self, path):

        image = self.image.copy()
        image = self.paint(image)
        cv2.imwrite(path, image)

    def display(self, image, boundingBox=(800,800), title='Image'):

        stopwatch.pause()

        if boundingBox:
            maxDimension = Dimension(boundingBox[0], boundingBox[1])
            displayDimension = Dimension(image.shape[1], image.shape[0])
            displayDimension.fitInside(maxDimension)
            image = cv2.resize(image, tuple(displayDimension))

        cv2.namedWindow(title, cv2.CV_WINDOW_AUTOSIZE)
        cv2.imshow(title, image)
        cv2.waitKey()

        stopwatch.unpause()

    def show(self, boundingBox=None, title="Image"):    #textImage

        #image = numpy.zeros(self.image.shape, numpy.uint8)
        image = self.image.copy()
        
        image = self.paint(image)

        self.display(image, boundingBox, title)

    def extractWords(self, sourceImage):

        image = sourceImage.copy()
        image = threshold(image)

        tempImageFile = os.path.join('src', 'tempImage.tiff')
        tempTextFile = os.path.join('src', 'tempText')

        mask = numpy.zeros(image.shape, numpy.uint8)
        singleWord = numpy.zeros(image.shape, numpy.uint8)
