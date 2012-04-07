import direct.directbase.DirectStart
from direct.showbase.ShowBase import ShowBase
from direct.gui.DirectGui import *
from panda3d.core import Vec3, Vec4, Point3, Point4
from direct.showbase.DirectObject import DirectObject
import random
import sys
import math
from pandac.PandaModules import CollisionHandlerQueue, CollisionNode, CollisionSphere, CollisionTraverser, BitMask32, CollisionRay
from direct.showbase.ShowBase import Plane, ShowBase, Vec3, Point3, CardMaker 

#VERSION 0.1.1
#THIRD VERSION BUMP FOR ANY CHANGE
#SECOND VERSION BUMP IF A MAJOR FEATURE HAS BEEN DONE WITH
#FIRST VERSION BUMP IF THE GAME IS RC

class Body:
  def __init__(self,obj,mass,vel,acel):
    self.node = obj
    self.mass = mass
    self.vel = vel
    self.acel = acel


class World:
  def __init__(self):
    self.testmode = True
    
    base.setBackgroundColor(0, 0, 0)
    camera.setPos ( 0, 0, 0 )
    camera.setHpr ( 0, -90, 0 )
    self.sizescale = 1.6
    self.orbitscale = 10
    self.objects = []
    self.yearscale = 60
    self.dayscale = self.yearscale / 365.0 * 5
    self.n = 8
    base.cTrav=CollisionTraverser()
    self.collisionHandler = CollisionHandlerQueue()
    DO=DirectObject()
    DO.accept('mouse1', self.mouseClick, ['down'])
    DO.accept('mouse1-up', self.mouseClick, ['up'])
    self.plane = Plane(Vec3(0, 0, 1), Point3(0, 0, 0))
    if not self.testmode:
      mySound = base.loader.loadSfx("m2.mp3")
      mySound.play()
    self.debug = 0
    taskMgr.add(self.traverseTask, 'tsk_traverse')
    taskMgr.add(self.refreshPlanets, 'refresh')
    #taskMgr.doMethodLater(.1, self.traverseTask, "tsk_traverse")
    self.orbit_period_planet = [0]*self.n
    self.day_period_planet = [0]*self.n
    self.planet = [0]*self.n
    self.planet_tex = [0]*self.n
    self.orbit_root_planet = [0]*self.n
    self.loadPlanets()
    self.rotatePlanets()

  def loadPlanets(self):
    self.sky = loader.loadModel("models/solar_sky_sphere")
    self.sky.reparentTo(render)
    self.sky.setScale(100)
    if self.testmode:
      self.sky.setColor(0,0,0,0)
    else:
      self.sky_tex = loader.loadTexture("models/s.jpg")
      self.sky.setTexture(self.sky_tex, 1)
    self.sun = loader.loadModel("models/planet_sphere")
    if not self.testmode:
      self.sun_tex = loader.loadTexture("models/s%s.jpg"%(int(random.random()*6)))
      self.sun.setTexture(self.sun_tex, 1)
    self.sun.reparentTo(render)
    self.sun.setScale(2 * self.sizescale)
    self.sunCollider = self.sun.attachNewNode(CollisionNode('sunnode'))
    self.sunCollider.node().addSolid(CollisionSphere(0, 0, 0, 1))
    base.cTrav.addCollider(self.sunCollider, self.collisionHandler)
    self.objects.append(Body(self.sun,1,Vec3(0,0,0),Vec3(0,0,0)))


    for i in range(self.n):
      self.planet = loader.loadModel("models/planet_sphere")
      if not self.testmode:
        self.planet_tex = loader.loadTexture("models/p%s.jpg"%(int(random.random()*9)))
        self.planet.setTexture(self.planet_tex, 1)
      self.planet.reparentTo(render)
      seed = random.random()
      seed2 = random.random()
      self.planet.setPos( (10*(seed-0.5) * self.orbitscale, 10*(seed2-0.5) * self.orbitscale, 0))
      self.planet.setScale((seed+0.3) * self.sizescale)
      self.planetCollider = self.planet.attachNewNode(CollisionNode('planetnode%d'%i))
      self.planetCollider.node().addSolid(CollisionSphere(0, 0, 0, 1))
      base.cTrav.addCollider(self.planetCollider, self.collisionHandler)
      self.objects.append(Body(self.planet,0.001,Vec3(0,0,0),Vec3(0,0,0)))


    for i in range(len(self.objects)):
      if i != 0:
        vts = self.objects[0].node.getPos() - self.objects[i].node.getPos()
        r = vts.length()
        vts.normalize()
        k = math.pi/2
        vts = Vec3(vts[0]*math.cos(k)+vts[1]*math.sin(k),vts[0]*-math.sin(k)+vts[1]*math.cos(k),0)
        vts = vts*math.sqrt(self.objects[0].mass/r) #tocheck
        self.objects[i].vel = Vec3(vts[0],vts[1],vts[2])
      else: self.objects[i].vel = Vec3(0,0,0)
      self.objects[i].acel = Vec3(0,0,0)

  def refreshPlanets(self,task):
    for i in range(len(self.objects)):
      a = Vec3(0,0,0)
      for j in range(len(self.objects)):
        if i != j:
          vec = self.objects[j].node.getPos() - self.objects[i].node.getPos()
          vec.normalize()
          vec *= self.objects[j].mass
          vec /= (self.objects[i].node.getPos() - self.objects[j].node.getPos()).lengthSquared()
          a += vec
      self.objects[i].vel = self.objects[i].vel + a
      self.objects[i].acel = a
    for i in range(len(self.objects)):
      if self.objects[i].mass <= 1:
        self.objects[i].node.setPos(self.objects[i].node.getPos() + self.objects[i].vel)
    return task.again


  def traverseTask(self,task):
    self.collisionHandler.sortEntries()
    for i in range(self.collisionHandler.getNumEntries()):
      entry = self.collisionHandler.getEntry(i)
      for j in range(len(self.objects)):
        if entry.getIntoNodePath().getParent().getPos() == self.objects[j].node.getPos() and self.objects[j].mass <= 1:
          self.objects.pop(j)
          entry.getIntoNodePath().getParent().detachNode()
          break
      print "Collision: into",entry.getIntoNode().getName()
    return task.again


  def mouseClick(self,status):
    if base.mouseWatcherNode.hasMouse(): 
      mpos = base.mouseWatcherNode.getMouse() 
      pos3d = Point3() 
      nearPoint = Point3() 
      farPoint = Point3() 
      base.camLens.extrude(mpos, nearPoint, farPoint) 
      if self.plane.intersectsLine(pos3d, 
          render.getRelativePoint(camera, nearPoint), 
          render.getRelativePoint(camera, farPoint)): 
        #print "Mouse ray intersects ground plane at ", pos3d
        if status == "down":
          self.blackhole = loader.loadModel("models/planet_sphere")
          if not self.testmode:
            self.blackhole_tex = loader.loadTexture("models/bh.jpg")
            self.blackhole.setTexture(self.blackhole_tex, 1)
          self.blackhole.reparentTo(render)
          self.blackhole.setPos(pos3d)
          self.blackhole.setScale(2)
          self.blackholeCollider = self.blackhole.attachNewNode(CollisionNode('bhnode'))
          self.blackholeCollider.node().addSolid(CollisionSphere(0, 0, 0, 1))
          base.cTrav.addCollider(self.blackholeCollider, self.collisionHandler)
          self.objects.append(Body(self.blackhole,7,Vec3(0,0,0),Vec3(0,0,0)))
        if status == "test":
          self.whitehole = loader.loadModel("models/planet_sphere")
          if not self.testmode:
            self.whitehole_tex = loader.loadTexture("models/bh.jpg")
            self.whitehole.setTexture(self.whitehole_tex, 1)
          self.whitehole.reparentTo(render)
          self.whitehole.setPos(pos3d)
          self.whitehole.setScale(2)
          self.whiteholeCollider = self.whitehole.attachNewNode(CollisionNode('bhnode'))
          self.whiteholeCollider.node().addSolid(CollisionSphere(0, 0, 0, 1))
          base.cTrav.addCollider(self.whiteholeCollider, self.collisionHandler)
          self.objects.append(Body(self.whitehole,-3,Vec3(0,0,0),Vec3(0,0,0)))



  def rotatePlanets(self):
    self.day_period_sun = self.sun.hprInterval(20, Vec3(360, 0, 0))

    #for i in range(self.n):
    #  seed = random.random()
    #  
    #  self.day_period_planet[i] = self.planet[i].hprInterval(
    #    ((seed+1) * self.dayscale), Vec3(360, 0, 0))

    self.day_period_sun.loop()

    #for i in range(self.n):
    #  self.day_period_planet[i].loop()


  
w = World()
run()


