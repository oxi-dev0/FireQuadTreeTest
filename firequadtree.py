import pygame
import math
import random
from vector2d import Vector2D

def Lerp(a,b,t):
     return a*(1-t) + b*t

def Remap(v, inMin, inMax, outMin, outMax):
    return outMin + (v - inMin) * (outMax - outMin) / (inMax - inMin)

def Clamp(v, min, max):
    if v > max:
        v = max
    if v < min:
        v = min
    return v

screenSize = Vector2D(1280, 720)

pygame.init()
screen = pygame.display.set_mode((screenSize.x, screenSize.y))
clock = pygame.time.Clock()
running = True
deltaTime = 0

class CellState:
    Empty = 0
    Ignited = 1

class RenderMode:
    Temperature = 0
    Fuel = 1
    MAX = 2

class Dir:
    N = 0
    E = 1
    S = 2
    W = 3

    @staticmethod
    def Reverse(dir):
        if dir == Dir.N:
            return Dir.S
        if dir == Dir.E:
            return Dir.W
        if dir == Dir.S:
            return Dir.N
        if dir == Dir.W:
            return Dir.E
        
class PosDir:
    NW = 0
    NE = 1
    SW = 2
    SE = 3

    @staticmethod
    def Mirror(pos, dir:Dir):
        if dir == Dir.N or dir == Dir.S:
            if pos == PosDir.NW:
                return PosDir.SW
            if pos == PosDir.NE:
                return PosDir.SE
            if pos == PosDir.SW:
                return PosDir.NW
            if pos == PosDir.SE:
                return PosDir.NE
        if dir == Dir.E or dir == Dir.W:
            if pos == PosDir.NW:
                return PosDir.NE
            if pos == PosDir.SW:
                return PosDir.SE
            if pos == PosDir.NE:
                return PosDir.NW
            if pos == PosDir.SE:
                return PosDir.SW

dirToPos = {
    Dir.N:[PosDir.NE,PosDir.NW],
    Dir.E:[PosDir.NE,PosDir.SE],
    Dir.S:[PosDir.SE,PosDir.SW],
    Dir.W:[PosDir.NW,PosDir.SW]
}

transmitSpeed = 1 # temp/s
ignitionTemp = 200
clickTemp = 300
burnSpeed = 0.5 # fuel/s
burnTempRate = 250 # temp/s
renderMode = RenderMode.Fuel

tempColorRange = [(0,pygame.Color(150,150,150)), (ignitionTemp,pygame.Color(255,100,100))]
fuelColorRange = [(0,pygame.Color(150,150,150)), (100,pygame.Color(100,255,100))]

class RuntimeData:
    def __init__(self):
        self.temperature = 0
        self.deltaT = 0
        self.fuel = 100

class QuadtreeNode:
    #stateColors = [pygame.Color(150,150,150), pygame.Color(200,100,100), pygame.Color(100,100,200)]
    borderColor = pygame.Color(0,0,0)
    borderSize = 1

    def __init__(self, origin:Vector2D, extents:Vector2D, parent=None, quadrantDir:PosDir=PosDir.NE):
        self.origin = origin
        self.extents = extents
        self.parent = parent
        self.quadrantDir = quadrantDir
        self.quadrants = [None, None, None, None]
        self.area = self.extents.x * self.extents.y

        self.state = CellState.Empty
        self.neighbours = {Dir.N:[], Dir.E:[], Dir.S:[], Dir.W:[]}
        self.runtimeData = RuntimeData()
        self.concentration = 1 - (self.extents.x*self.extents.y)/(screenSize.x*screenSize.y) # concentration is so that bigger cells dont transmit as fast as smaller cells
    
    def IsLeaf(self):
        return self.quadrants[0] == None
    
    def IsRoot(self):
        return self.parent == None
    
    def Subdivide(self):
        if not self.IsLeaf():
            return
        
        self.runtimeData = None
        self.quadrants[0] = QuadtreeNode(self.origin + (Vector2D(0,0) * (self.extents/2)), self.extents/2, self, PosDir.NW)
        self.quadrants[1] = QuadtreeNode(self.origin + (Vector2D(1,0) * (self.extents/2)), self.extents/2, self, PosDir.NE) 
        self.quadrants[2] = QuadtreeNode(self.origin + (Vector2D(0,1) * (self.extents/2)), self.extents/2, self, PosDir.SW)
        self.quadrants[3] = QuadtreeNode(self.origin + (Vector2D(1,1) * (self.extents/2)), self.extents/2, self, PosDir.SE)
    
    @staticmethod
    def AxisToQuadrant(xIndex, yIndex):
        return (xIndex * 1) + (yIndex * 2)

    def Find(self, point:Vector2D): 
        if self.IsLeaf():
            return self

        positionRatio = ((point - self.origin)/self.extents)*2
        xIndex = math.floor(positionRatio.x)
        yIndex = math.floor(positionRatio.y)
        return self.quadrants[QuadtreeNode.AxisToQuadrant(xIndex, yIndex)].Find(point)
    
    def FindGreaterNeighbour(self, dir:Dir):
        if self.IsRoot():
            return None # this is a bit of a weird way to handle root
        
        posOpts = dirToPos[Dir.Reverse(dir)]
        if self.quadrantDir == posOpts[0]:
            return self.parent.quadrants[PosDir.Mirror(posOpts[0], dir)]
        if self.quadrantDir == posOpts[1]:
            return self.parent.quadrants[PosDir.Mirror(posOpts[1], dir)]
        
        node = self.parent.FindGreaterNeighbour(dir)
        if node == None or node.IsLeaf():
            return node
        
        return node.quadrants[PosDir.Mirror(self.quadrantDir, dir)]
    
    def FindLesserNeighbours(self, top, dir:Dir):
        neighbours = []
        candidates = []
        if top != None:
            candidates = [top]

        while len(candidates) > 0:
            if candidates[0].IsLeaf():
                neighbours.append(candidates[0])
            else:
                posOpts = dirToPos[Dir.Reverse(dir)]
                candidates.append(candidates[0].quadrants[posOpts[0]])
                candidates.append(candidates[0].quadrants[posOpts[1]])
            candidates.remove(candidates[0])
        
        return neighbours
    
    def FindNeighbours(self, dir:Dir):
        top = self.FindGreaterNeighbour(dir)
        return self.FindLesserNeighbours(top, dir)
    
    def BakeNeighbours(self):
        if self.IsLeaf():
            for dir in [Dir.N, Dir.E, Dir.S, Dir.W]:
                self.neighbours[dir] = self.FindNeighbours(dir)
        else:
            for quadrant in self.quadrants:
                quadrant.BakeNeighbours()

    def Simulate(self, deltaTime):
        if self.IsLeaf():
            if self.runtimeData.temperature > ignitionTemp*(1-self.concentration) and self.runtimeData.fuel > 0:
                self.state = CellState.Ignited
            if self.state == CellState.Ignited:
                self.runtimeData.fuel -= burnSpeed
                self.runtimeData.temperature += burnTempRate * (1-self.concentration) * deltaTime
                if self.runtimeData.fuel <= 0:
                    self.runtimeData.fuel = 0
                    self.state = CellState.Empty

            for dir in [Dir.N, Dir.E, Dir.S, Dir.W]:
                for neighbour in self.neighbours[dir]:
                    # this is only from this cell to the neighbour
                    transferAmount = self.runtimeData.temperature * self.concentration * (transmitSpeed * deltaTime) * min(neighbour.area/self.area, 1)
                    neighbour.runtimeData.deltaT += transferAmount
                    self.runtimeData.deltaT -= transferAmount
                if len(self.neighbours[dir]) == 0:
                    self.runtimeData.deltaT -= self.runtimeData.temperature * self.concentration * (transmitSpeed*deltaTime)
        else:
            for quadrant in self.quadrants:
                quadrant.Simulate(deltaTime)

    def Apply(self):
        if self.IsLeaf():
            self.runtimeData.temperature += self.runtimeData.deltaT
            self.runtimeData.deltaT = 0
        else:
            for quadrant in self.quadrants:
                quadrant.Apply()

    def Render(self, surface):
        if self.IsLeaf():
            color = pygame.Color(150, 150, 150)
            colorRange = tempColorRange
            value = self.runtimeData.temperature/(1-self.concentration)
            if renderMode == RenderMode.Fuel:
                colorRange = fuelColorRange
                value = self.runtimeData.fuel
            else:
                colorRange = tempColorRange
                value = self.runtimeData.temperature/(1-self.concentration)
            tempAlpha = Remap(value, colorRange[0][0], colorRange[1][0], 0, 1)
            tempAlpha = Clamp(tempAlpha, 0, 1)
            colorR = Lerp(colorRange[0][1].r, colorRange[1][1].r, tempAlpha)
            colorG = Lerp(colorRange[0][1].g, colorRange[1][1].g, tempAlpha)
            colorB = Lerp(colorRange[0][1].b, colorRange[1][1].b, tempAlpha)
            color = pygame.Color(int(colorR), int(colorG), int(colorB))

            pygame.draw.rect(surface, QuadtreeNode.borderColor, pygame.Rect(self.origin.x, self.origin.y, self.extents.x, self.extents.y))
            pygame.draw.rect(surface, color, pygame.Rect(self.origin.x+QuadtreeNode.borderSize, self.origin.y+QuadtreeNode.borderSize, self.extents.x-(QuadtreeNode.borderSize*2), self.extents.y-(QuadtreeNode.borderSize*2)))
            if self.state == CellState.Ignited:
                pygame.draw.circle(surface, pygame.Color(255,0,0), (self.origin.x + self.extents.x/2, self.origin.y + self.extents.y/2), 5)
        else:
            for quadrant in self.quadrants:
                quadrant.Render(surface)

    def ClearState(self):
        self.state = 0
        if not self.IsLeaf():
            for quadrant in self.quadrants:
                quadrant.ClearState()

    def Clicked(self):
        self.runtimeData.temperature = clickTemp * (1-self.concentration)
        print(self.concentration)

root = QuadtreeNode(Vector2D.Zero(), screenSize)

def RecursiveSplitPrep(node:QuadtreeNode, depth:int):
    if depth < 6:
        if random.randint(0, int(depth/3)) == 0:
            node.Subdivide()
            for quadrant in node.quadrants:
                RecursiveSplitPrep(quadrant, depth+1)

RecursiveSplitPrep(root, 0)
root.BakeNeighbours()

def Render():
    root.Simulate(deltaTime)
    root.Apply()
    root.Render(screen)

while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            running = False
            continue
        if event.type == pygame.MOUSEBUTTONDOWN:
            pos = pygame.mouse.get_pos()
            #root.ClearState()
            root.Find(Vector2D(pos[0], pos[1])).Clicked()
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_TAB:
                renderMode += 1
                if renderMode >= RenderMode.MAX:
                    renderMode = RenderMode.Temperature
    
    screen.fill("white")

    Render()

    pygame.display.flip()
    deltaTime = clock.tick(60)/1000

pygame.quit()