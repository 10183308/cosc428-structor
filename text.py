import cv2
import numpy
import math

import colors
import geometry as g
from box import Box
from dimension import Dimension

class AbstractLineCollection:

    def __init__(self, lines=[]):
        self.lines = lines
        self.update()

    def append(self, line):

        self.lines.append(line)
        self.update()

    def extend(self, lines):

        for line in lines:
            self.append(line)

    def peekStart(self, num=1):
        if num == 1:
            return self.lines[0]
        else:
            return self.lines[:num]

    def pull(self, num=1):

        first = self.lines[:num]
        self.lines = self.lines[num:]
        if num == 1:
            return first[0] #unwrap
        else:
            return first

    def pop(self):
        return self.lines.pop()

    def __getitem__(self, val):
        return self.lines.__getitem__(val)

    def __len__(self):
        return self.lines.__len__()

    def paint(self, image, color):

        try:
            print "page skew: %f" %self.avgAngle.degrees()
        except AttributeError:
            pass

        for line in self.lines:
            image = line.paint(image, color)

        return image



class FragmentCollection(AbstractLineCollection):

    def __init__(self, lines=[]):
        AbstractLineCollection.__init__(self, lines)

    def __reversed__(self):
        return FragmentCollection(reversed(self.lines))

    def update(self):

        # sort lines by the y-position of the first word in each line
        yPosition = lambda line: line.words[0].center[1]
        self.lines = sorted(self.lines, key=yPosition)

class LineCollection(AbstractLineCollection):

    def __init__(self, lines=[]):
        AbstractLineCollection.__init__(self, lines)

    def __reversed__(self):
        return LineCollection(reversed(self.lines))

    def update(self):

        # calculate the average angle of all lines
        self.avgAngle = g.Angle(0)
        angles = [line.angle for line in self.lines if line.angle != None]
        if len(angles):
            self.avgAngle = g.Angle.average(angles)

        # sort lines by the y-position of the first word in each line
        yPosition = lambda line: g.Point(line.box.center.center).rotate(self.avgAngle).y
        self.lines = sorted(self.lines, key=yPosition)


class Line:

    def __init__(self, firstWord):

        self.words = [firstWord]
        self.angle = None
        self.totalArea = None
        self.avgArea = None
        self.box = None

        self.leftIndent = None      # distance to the left margin
        self.rightIndent = None     # distance to the right margin

        self.isParagraphStart = False
        self.isParagraphEnd = False
        self.isCentered = False
        self.isHorizontalRule = False

        self.exploreGraph()
        self.update()   # sort words by horizontal position, and calculate the lines's angle, contour, and box.

    def exploreGraph(self):
        # Do a depth-first search on the graph, and add any found words to the self.words list. This
        # basically means, "All connected words are part of the same line."

        # seenButNotExplored holds all words that we have discovered but which haven't been searched
        # themselves. They might contain links to other (new) words.
        seenButNotExplored = self.words[:]  # the [:] is to ensure that we have a separate object.
        for word in seenButNotExplored:
            word.isSeen = True

        while len(seenButNotExplored) > 0:

            wordBeingSearched = seenButNotExplored.pop()
            neighbours = []

            neighbours.extend(wordBeingSearched.rightLinks)
            neighbours.extend(wordBeingSearched.leftLinks)

            for neighbour in neighbours:
                if neighbour.isSeen == False:     # note that word.isSeen is always set if a word is already part of the line.
                    neighbour.isSeen = True
                    seenButNotExplored.append(neighbour)
                    self.words.append(neighbour)
                    neighbour.parentLine = self

    def split(self, page):
        # this is called if the line has a 'suspicious' height, and it should try to split the line
        # into two (or more) separate lines.

        connections = []    # each entry should be an array of the form [wordOne, wordTwo]
        for wordOne in self.words:

            neighbours = []
            neighbours.extend(wordOne.rightLinks)
            neighbours.extend(wordOne.leftLinks)

            for wordTwo in self.words:
                if wordOne is wordTwo:
                    continue
                if ([wordOne, wordTwo] in connections) or ([wordTwo, wordOne] in connections) :
                    continue    # we don't want double-ups
                if wordTwo in neighbours:
                    connections.append([wordOne, wordTwo])

        candidatePairs = []
        for pair in connections:

            words = self.words[:]   # [:] results in a copy of the list.
            for word in words:
                word.isSeen = False

            pair[0].isSeen = True  # This is equivalent to an impenetrable wall in the graph search.
            pair[1].isSeen = True

            lineOne = Line(pair[0])
            lineTwo = Line(pair[1])

            if (lineOne.box.height < 55) and (lineTwo.box.height < 55):
                return [lineOne, lineTwo]
            else:
                candidatePairs.append([lineOne, lineTwo])



        #for pair in candidatePairs:

            #boundingBox = (700,700)
            #title = 'foo'
            #image = page.image.copy()

            #for line in pair:
                #image = line.paint(image, colors.BURNT_YELLOW)

            #if boundingBox:
                #maxDimension = Dimension(boundingBox[0], boundingBox[1])
                #displayDimension = Dimension(image.shape[1], image.shape[0])
                #displayDimension.fitInside(maxDimension)
                #image = cv2.resize(image, tuple(displayDimension))

            #cv2.namedWindow(title, cv2.CV_WINDOW_AUTOSIZE)
            #cv2.imshow(title, image)
            #cv2.waitKey()

        return [self]

    def update(self):

        # sort words by their x-position
        xPosition = lambda word: word.center[0]
        self.words = sorted(self.words, key=xPosition)

        #calculate the line's angle by fitting a least-squares line to the word centers.
        trend = g.Line(word.center for word in self.words)
        self.angle = trend.angle

        # find the Box (minAreaRect) around all the words in the line. This is different from the 'raw'
        # boxes we started with, because the box we are creating here is designed to enclose a specific
        # set of words (not just a guess of where the words might be).
        points = []
        for word in self.words:
            for point in word.contour:
                points.append(point)
        points = numpy.array(points)    # This needs to have the format [ [[a,b]], [[c,d]] ]
        self.box = Box(points)
        self.center = self.box.center.center

        self.totalArea = 0
        for word in self.words:
            self.totalArea += word.getArea()
        self.avgArea = float(self.totalArea) / len(self.words)

    def determineIndents(self, margin):

        # All calculations are done in the 'corrected' frame of reference, hence the calls to .rotate

        leftEdgeOfText = g.Point(self.box.center.left).rotate(margin.angle)
        rightEdgeOfText = g.Point(self.box.center.right).rotate(margin.angle)

        pointOnLeftMarginLine = margin.left.start.rotate(margin.angle)
        pointOnRightMarginLine = margin.right.start.rotate(margin.angle)

        leftProjection = g.Point(pointOnLeftMarginLine.x, leftEdgeOfText.y)
        rightProjection = g.Point(pointOnRightMarginLine.x, rightEdgeOfText.y)

        self.leftIndent = g.Point.distance(leftEdgeOfText, leftProjection)
        self.rightIndent = g.Point.distance(rightEdgeOfText, rightProjection)

    def setFlags(self, margin):

        if 1280 < self.box.width < 1330:
            if self.box.height < 20:
                self.isHorizontalRule = True

        if 30 < self.leftIndent < 60:
            self.isParagraphStart = True
        if self.rightIndent > 50:
            self.isParagraphEnd = True

        if self.leftIndent > 50 and self.rightIndent > 50:
            difference = abs(self.leftIndent - self.rightIndent)
            if difference < 50:
                self.isCentered = True

    def __len__(self):
        return self.words.__len__()

    def paint(self, image, color, centerLine=False, box=False):

        #for word in self.words:
        #    image = word.paint(image, colors.RED)

        if centerLine:
            start = self.box.center.left
            end = self.box.center.right
            image = g.Line([start, end]).paint(image, color)

        if box:
            image = self.box.paint(image, color, width=5)

        return image

class Word:

    def __init__(self, contour):

        self.contour = contour
        self.center = self.getCenterOfMass(contour)

        self.rect = cv2.minAreaRect(contour)    # rect = ((center_x,center_y),(width,height),angle)
        self.points = self.rectToPoints(self.rect)

        self.start, self.end = self.getEndPoints(self.points)

        self.rightCandidates = []   # each element in the list will have the form [ WordInstance, distanceScore ]
        self.leftCandidates = []    # candidates for 'going leftwards along the line', i.e. backwards.
        self.rightLinks = []
        self.leftLinks = []

        self.parentLine = None      # this will eventually hold a reference to a Line instance.
        self.isSeen = False         # this is a flag used in the depth-first search of a graph fragment.

    def getCenterOfMass(self, contour):

        moments = cv2.moments(contour)

        centroidX = int( moments['m10'] / moments['m00'] )
        centroidY = int( moments['m01'] / moments['m00'] )

        return (centroidX, centroidY)

    def rectToPoints(self, rect):

        points = cv2.cv.BoxPoints(rect)             # Find four vertices of rectangle from above rect
        points = numpy.int0(numpy.around(points))   # Round the values and make them integers
        return points

    def getEndPoints(self, points):

        points  = sorted(points, key=lambda point: point[0]) # sort by x position.
        left = sorted(points[:2], key=lambda point: point[1])  # [top-left, bottom-left]
        right = sorted(points[2:], key=lambda point: point[1]) # [top-right, bottom-right]

        start = Word.midpoint(left[0], left[1]) # midpoint of top-left and bottom-left
        end = Word.midpoint(right[0], right[1]) # midpoint of top-right and bottom-right

        return start, end

    def getArea(self):
        return cv2.contourArea(self.contour)

    def selectCandidates(self):

        if len(self.rightCandidates):
            best = min(self.rightCandidates, key=lambda element: element[1])[0]
            self.rightLinks.append(best)
            best.leftLinks.append(self)

        if len(self.leftCandidates):
            best = min(self.leftCandidates, key=lambda element: element[1])[0]
            self.leftLinks.append(best)
            best.rightLinks.append(self)

    def paint(self, image, color):

        #image = g.Point(self.center).paint(image, colors.RED)    # draw a dot at the word's center of mass.

        centerline = g.Line([self.start, self.end])
        image = centerline.paint(image, color)

        if len(self.rightLinks) is not None:
            for word in self.rightLinks:
                connector = g.Line([self.end, word.start])
                image = connector.paint(image, color)
        if len(self.leftLinks) is not None:
            for word in self.leftLinks:
                connector = g.Line([self.start, word.end])
                image = connector.paint(image, color)

        return image

    @staticmethod
    def midpoint(start, end):

        midX = float(start[0]+end[0]) / 2
        midY = float(start[1]+end[1]) / 2

        return (midX, midY)
