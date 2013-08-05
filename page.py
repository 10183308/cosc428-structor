import cv2
import math
import numpy
import subprocess
import os

import colors
import geometry as g
from box import Box
import text
from dimension import Dimension
from margin import Margin, NaiveMargin
from stopwatch import Stopwatch
from content import Content, BoilerPlate

stopwatch = Stopwatch()

def getWeightedDistance(kernel, pointOne, pointTwo):

    rise = float(pointOne[1]) - float(pointTwo[1])

    run  = float(pointOne[0]) - float(pointTwo[0])

    weightedRise = rise*kernel[1]
    weightedRun = run*kernel[0]
    distance = math.sqrt(weightedRise**2 + weightedRun**2)

    return distance

def threshold(image, threshold=colors.greyscale.MID_GREY, method=cv2.THRESH_BINARY_INV):
    retval, dst = cv2.threshold(image, threshold, colors.greyscale.WHITE, method)
    return dst

class Page:

    def __init__(self, path, showSteps=False):

        stopwatch.reset(path)

        self.showSteps = showSteps
        greyscaleImage = cv2.imread(path, cv2.CV_LOAD_IMAGE_GRAYSCALE)
        colorImage = cv2.imread(path, cv2.CV_LOAD_IMAGE_COLOR)

        if self.showSteps:
            self.display(colorImage)

        self.image = colorImage
        self.margin, self.lines = self.getBuildingBlocks(greyscaleImage, colorImage)
        self.boilerPlate = self.getBoilerPlate()

        if self.showSteps:
            img = colorImage.copy()
            self.display(img)

            img = self.boilerPlate.paint(img, color=colors.BLACK)
            self.display(img)

        self.content = Content(self.lines, self.isChapterStart())

        if self.showSteps:
            for item in self.content.content:
                img = item.paint(img)
                self.display(img)

        stopwatch.lap("found content")
        stopwatch.endRun()

    def getBuildingBlocks(self, greyscale, colorImage):

        margin = Margin()
        lines = text.LineCollection()

        words = self.getWords(greyscale)
        stopwatch.lap("got words")

        if self.showSteps:
            image = numpy.zeros(colorImage.shape, numpy.uint8)
            for word in words:
                box = Box(word.contour)
                image = box.paint(image, colors.WHITE)
            self.display(image)


        words = self.linkWords(words)
        stopwatch.lap("formed word graph")

        candidateLines = self.getLines(words)
        lines = NaiveMargin(candidateLines).selectLines()
        stopwatch.lap("found lines")

        if self.showSteps:
            image = numpy.zeros(colorImage.shape, numpy.uint8)
            for line in lines:
                for word in line.words:
                    box = Box(word.contour)
                    image = box.paint(image, colors.MID_GREY, width=2)

                    connector = g.Line([word.start, word.end])
                    image = connector.paint(image, colors.ORANGE)

                    if len(word.rightLinks) is not None:
                        for target in word.rightLinks:
                            connector = g.Line([word.end, target.start])
                            image = connector.paint(image, colors.RED)

                    if len(word.leftLinks) is not None:
                        for target in word.leftLinks:
                            connector = g.Line([word.start, target.end])
                            image = connector.paint(image, colors.RED)
            self.display(image)

        margin.fit(lines)
        stopwatch.lap("found margin")
        if self.showSteps:
            image = margin.paint(image, colors.WHITE)
            self.display(image)



        for line in lines:
            line.determineIndents(margin)
            line.setFlags(margin)

        return margin, lines

    def getWords(self, sourceImage):

        words = []
        blurKernel = (11,11)

        image = sourceImage.copy()
        image = threshold(image)
        image = cv2.GaussianBlur(image, ksize=blurKernel, sigmaX=0)
        image = threshold(image, cv2.THRESH_OTSU, method=cv2.THRESH_BINARY)

        if self.showSteps:
            self.display(image)

        contours = self.getContours(image)

        for contour in contours:
            word = text.Word(contour)
            if word.getArea() > 50:
                words.append(word)

        return words

    def getContours(self, sourceImage, threshold=-1):

        image = sourceImage.copy()
        blobs = []
        topLevelContours = []

        contours, hierarchy = cv2.findContours(image, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        for i in range(len(hierarchy[0])):

            if len(contours[i]) > 2:    # 1- and 2-point contours have a divide-by-zero error in calculating the center of mass.

                # bind each contour with its corresponding hierarchy context description.
                obj = {'contour': contours[i], 'context': hierarchy[0][i]}
                blobs.append(obj)

        for blob in blobs:
            parent = blob['context'][3]
            if parent <= threshold: # no parent, therefore a root
                topLevelContours.append(blob['contour'])

        return topLevelContours

    def linkWords(self, words):

        kernel = [1, 1.5]   # [horizontal scaling factor, vertical scaling factor]
        distanceThreshold = 50  # in pixels, but remember to account for scaling factors.

        for i, base in enumerate(words):
            for j, target in enumerate(words):

                if i == j:
                    continue    # we don't care about the distance from an word's end to it's own beginning.

                endToStartDistance = getWeightedDistance(kernel, base.end, target.start)
                if endToStartDistance < distanceThreshold:
                    base.rightCandidates.append([target, endToStartDistance])

                startToEndDistance = getWeightedDistance(kernel, base.start, target.end)
                if startToEndDistance < distanceThreshold:
                    base.leftCandidates.append([target, startToEndDistance])

        for word in words:
            word.selectCandidates()

        return words

    def getLines(self, words):

        candidateLines = text.FragmentCollection()

        while len(words) > 0:
            rootWord = words.pop()
            line = text.Line(rootWord)  # this also involves exploring the word graph and adding any linked words.

            if line.avgArea > 50:     # ignore small dots.

                if 80 < line.box.height < 300:
                    lines = line.split(self)
                    candidateLines.extend(lines)
                else:
                    candidateLines.append(line)

            # Make sure page.words only contains words which aren't yet assigned to a line.
            words[:] = [word for word in words if word.parentLine is None]

        return candidateLines

    def getBoilerPlate(self):

        boilerPlate = BoilerPlate()    # this is basically an empty object.

        if self.isChapterStart():
            boilerPlate.pageNum = self.lines.pop()
        else:
            headerLines = self.lines.pull(2)
            headerLines = sorted(headerLines, key=lambda line: line.box.width) # sort by length.

            boilerPlate.pageNum = headerLines[0] # the page number should always be the shorter of the two.

            if boilerPlate.pageNum.leftIndent < boilerPlate.pageNum.rightIndent:
                # |(pagenum)         (bookTitle)                |
                boilerPlate.bookTitle = headerLines[1]
                stopwatch.lap("found pageNum, bookTitle")
            else:
                # |                (chapterTitle)      (pagenum)|
                boilerPlate.chapterTitle = headerLines[1]
                stopwatch.lap("found pageNum, chapterTitle")

        return boilerPlate

    def isChapterStart(self):

        numHorizontalRules = 0
        for line in self.lines:
            if line.isHorizontalRule:
                numHorizontalRules += 1

        return ( (numHorizontalRules >= 2) and (self.margin.height < 1900) )

    def paint(self, image):

        image = self.margin.paint(image, color=colors.BLUE)
        image = self.boilerPlate.paint(image, color=colors.BLACK)
        image = self.content.paint(image)

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
