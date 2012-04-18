import direct.directbase.DirectStart
from direct.showbase.ShowBase import ShowBase
from direct.gui.DirectGui import *
from panda3d.core import Vec3, Vec4, Point3, Point4
from direct.showbase.DirectObject import DirectObject
import random
import sys
import math
from direct.directtools.DirectGeometry import LineNodePath
from pandac.PandaModules import CollisionHandlerQueue, CollisionNode, CollisionSphere, CollisionTraverser, BitMask32, CollisionRay
from direct.showbase.ShowBase import Plane, ShowBase, Vec3, Point3, CardMaker 

from direct.directbase.DirectStart import *
from pandac.PandaModules import *


#VERSION 0.1.3
#THIRD VERSION BUMP FOR ANY CHANGE
#SECOND VERSION BUMP IF A MAJOR FEATURE HAS BEEN DONE WITH
#FIRST VERSION BUMP IF THE GAME IS RC

#TO BE IMPLEMENTED:

#--- Animation ---
#to add some effects as explosions, black hole suction, meteorite crashing and the like with Particle Panel

#--- Sound ---
#to add sound to all in-game events (explosions, alert beeps, etc)

#---  Camera  ---
#to lock  camera rotation around axis Y
#to switch the camera controls, such as:
#LEFT CLICK (rotation around Z axis) -> RIGHT CLICK, A and D keys
#RIGHT CLICK (zoom) -> MOUSE WHEEL UP/DOWN

#--- Interface ---
#to add buttons and their respective callbacks to the lateral menu (self.menuRegion)
#Planets' lifebars
#Start Menu (optional)

#---   AI   ---
#"Smart Meteors": meteorites that calculates the angle to hit a planet so that such planet hits other one
#Planets' Races (optional)

#--- Others ---
#

class Body:
  #Wrapper of the pandaNode class to add extra attributes
  def __init__(self,obj,mass,vel,acel):
    #The node is a common pandaNode object
    self.node = obj
    #Just a float number that represents the mass of the body
    self.mass = mass
    #Both vel and acel are 3 dimensional vector objects of the Vec3 class
    self.vel = vel
    self.acel = acel


class World:
  def __init__(self):
    #Testmode disables all textures and sounds
    #Leave it as True unless you have all the textures and sound effects
    self.testmode = True
    
    #Creates the main region which displays the solar system itself
    #Also creates a new mouseWatcherNode so mouse picking works
    #according to the region clicked during the mouse callback
    self.mainRegion = base.cam.node().getDisplayRegion(0)
    self.mainRegion.setDimensions(0,0.8,0,1)
    base.mouseWatcherNode.setDisplayRegion(self.mainRegion)
    base.setBackgroundColor(0, 0, 0)
    camera.setPos ( 0, 0, 0 )
    camera.setHpr ( 0, -90, 0 )
    
    #Same procedure as above, but this is for the minimap
    self.minimapRegion = base.win.makeDisplayRegion(0.81, 0.99, 0.71, 0.98)
    self.minimapRegion.setSort(1)
    self.minimapRegion.setClearColor(VBase4(1, 1, 1, 1))
    self.minimapRegion.setClearColorActive(True)
    self.minimapRegion.setClearDepthActive(True)
    minimapc = render.attachNewNode(Camera('minicam'))
    self.minimapRegion.setCamera(minimapc)
    minimapc.setPos(0, 0, 270)
    minimapc.setHpr(0,-90,0)
    
    #Same procedure as above, but this is for the menu
    self.menuRegion = base.win.makeDisplayRegion(0.8,1,0,1)
    self.menuRegion.setSort(0)
    myCamera2d = NodePath(Camera('myCam2d'))
    lens = OrthographicLens()
    lens.setFilmSize(2, 2)
    lens.setNearFar(-1000, 1000)
    myCamera2d.node().setLens(lens)
    myRender2d = NodePath('myRender2d')
    myRender2d.setDepthTest(False)
    myRender2d.setDepthWrite(False)
    myCamera2d.reparentTo(myRender2d)
    self.menuRegion.setCamera(myCamera2d)
    aspectRatio = base.getAspectRatio()
    myAspect2d = myRender2d.attachNewNode(PGTop('myAspect2d'))
    myAspect2d.setScale(1.0 / aspectRatio, 1.0, 1.0)
    myAspect2d.node().setMouseWatcher(base.mouseWatcherNode)
    imageObject = OnscreenImage(image = 'models/menu.jpg', scale =  (1,1,1), parent = myRender2d)
    
    #Creates a line connecting planets when these are close enough to satisfy self.orbitscale.
    #Different values of self.caution define how far lines start to appear,
    #but will make more sense by the time others difficult levels get implemented
    self.caution = 0
    self.lines = LineNodePath(parent = render, thickness = 3.0, colorVec = Vec4(1, 0, 0, 1))
    self.sizescale = 1.6
    self.orbitscale = 10
    
    #Objects is the main array that keeps trace of all the Body type objects
    self.objects = []

    #Unimportant parameters
    self.yearscale = 60
    self.dayscale = self.yearscale / 365.0 * 5
    self.sizescale = 1.6
    self.orbitscale = 10

    #n defines the number of planets to be created
    self.n = 8

    #Creates the handler of collisions and makes it be referenced by self.collisionHandler
    base.cTrav=CollisionTraverser()
    self.collisionHandler = CollisionHandlerQueue()

    #Selection of callback functions
    DO=DirectObject()
    DO.accept('mouse1', self.mouseClick, ['down'])
    DO.accept('mouse1-up', self.mouseClick, ['up'])
    DO.accept('a', self.keyboardPress, ['a'])
    DO.accept('s', self.keyboardPress, ['s'])
    DO.accept('d', self.keyboardPress, ['d'])
    DO.accept('w', self.keyboardPress, ['w'])

    #Creation of the plane defined by the solar system (normal (0,0,1) and point(0,0,0))
    self.plane = Plane(Vec3(0, 0, 1), Point3(0, 0, 0))

    #Loads and plays the soundtrack if not in testmode
    if not self.testmode:
      mySound = base.loader.loadSfx("m2.mp3")
      mySound.play()

    #For later use only
    self.debug = 0

    #Adds the functions traverseTask and refreshPlanets to the taskManager
    #This makes both functions be called before every frame
    #traverseTask is responsible for treating collisions while
    #refreshPlanets is responsible for velocity and acceleration calculus
    taskMgr.add(self.traverseTask, 'tsk_traverse')
    #taskMgr.add(self.refreshPlanets, 'refresh')
    taskMgr.doMethodLater(0.01, self.refreshPlanets, 'refresh')

    #Initialization of several arrays (some are useless now, need further checking)
    self.orbit_period_planet = [0]*self.n
    self.day_period_planet = [0]*self.n
    self.planet = [0]*self.n
    self.planet_tex = [0]*self.n
    self.orbit_root_planet = [0]*self.n

    #Run the functions responsible for creating the planets and configuring their rotations
    self.loadPlanets()
    self.rotatePlanets()


  def loadPlanets(self):
    #This function is responsible for creating the bodies upon the start of the game

    #Loads the model for the sky (big ball surrounding the system)
    #The model in question is an inverted sphere (sphere with a negative normal vector)
    #This is used since we want to see the inside of the sphere, and also only treat
    #collisions when other objects leave the sphere
    self.sky = loader.loadModel("models/solar_sky_sphere")
    
    #Reparenting to 'render' is makes the model visible. Otherwise it wouldn't be renderized.
    self.sky.reparentTo(render)

    #Sets the size of the sky sphere
    self.sky.setScale(150)

    #Makes it just a black sphere if in testmode, otherwise loads the corresponding texture
    if self.testmode:
      self.sky.setColor(0,0,0,0)
    else:
      self.sky_tex = loader.loadTexture("models/s.jpg")
      self.sky.setTexture(self.sky_tex, 1)
    self.skyCollider = self.sky.attachNewNode(CollisionNode('skynode'))
    self.skyCollider.node().addSolid(CollisionInvSphere(0, 0, 0, 1))
    base.cTrav.addCollider(self.skyCollider, self.collisionHandler)


    #Exactly the same procedure as the sky sphere creation
    #The only difference is that a common sphere is used as the model
    self.sun = loader.loadModel("models/planet_sphere")
    if not self.testmode:
      self.sun_tex = loader.loadTexture("models/s%s.jpg"%(int(random.random()*6)))
      self.sun.setTexture(self.sun_tex, 1)
    self.sun.reparentTo(render)
    self.sun.setScale(2 * self.sizescale)

    #Creates a CollisionNode with a suitable name ('sunnode') and
    #attaches it to the sun pandaNode
    self.sunCollider = self.sun.attachNewNode(CollisionNode('sunnode'))

    #Adds a solid to the sunCollider node (a sphere with the same size
    #and position of its father node (in this case, the sun itself).
    self.sunCollider.node().addSolid(CollisionSphere(0, 0, 0, 1))

    #Adds the sunCollider node to the handler (to the FROM list, as default)
    base.cTrav.addCollider(self.sunCollider, self.collisionHandler)

    #Appends the sun Body object with mass 1 and zero velocity and acceleration
    self.objects.append(Body(self.sun,1,Vec3(0,0,0),Vec3(0,0,0)))

    #Same procedure as the sun creation, but with random textures, sizes and orbit radius.
    for i in range(self.n):
      self.planet = loader.loadModel("models/planet_sphere")
      if not self.testmode:
        self.planet_tex = loader.loadTexture("models/p%s.jpg"%(int(random.random()*9)))
        self.planet.setTexture(self.planet_tex, 1)
      self.planet.reparentTo(render)
      
      #Two seeds are created randomly, one for the X pos and size, the other for the Y pos
      seed = random.random()
      seed2 = random.random()
      
      self.planet.setPos( (10*(seed-0.5) * self.orbitscale, 10*(seed2-0.5) * self.orbitscale, 0))
      self.planet.setScale((seed+0.3) * self.sizescale)
      self.planetCollider = self.planet.attachNewNode(CollisionNode('planetnode%d'%i))
      self.planetCollider.node().addSolid(CollisionSphere(0, 0, 0, 1))
      base.cTrav.addCollider(self.planetCollider, self.collisionHandler)
      self.objects.append(Body(self.planet,0.001,Vec3(0,0,0),Vec3(0,0,0)))

    #Calculates and initializes the corresponding velocities for every planet
    #This is necessary for them to start with a correct orbit
    #The velocity has to be ortogonal to the acceleration vector, and its
    #module has to be sqrt(2m/r). The '2' and all other constants are ignored since
    #all masses are chosen arbitrarily.
    for i in range(len(self.objects)):
      #Ignores the sun, since it starts with zero acceleration and velocity
      if i != 0:
        #Gets the vector from the planet 'i' to the sun (vts = vector to sun)
        vts = self.objects[0].node.getPos() - self.objects[i].node.getPos()
        r = vts.length()

        #Normalizes the 'vector to sun' vector
        vts.normalize()
        k = math.pi/2

        #Rotates it by 90 degrees by applying a rotation matrix multiplication
        vts = Vec3(vts[0]*math.cos(k)+vts[1]*math.sin(k),vts[0]*-math.sin(k)+vts[1]*math.cos(k),0)

        #Sets its module as sqrt(m/r), where m is the mass of the sun
        vts = vts*math.sqrt(self.objects[0].mass/r)
        self.objects[i].vel = Vec3(vts[0],vts[1],vts[2])
      else: self.objects[i].vel = Vec3(0,0,0)
      
      #Every object starts with zero acceleration
      self.objects[i].acel = Vec3(0,0,0)

  def refreshPlanets(self,task):
    #This function is responsible for calculating the acceleration and velocity of
    #every Body, and then changing its position accordingly.
    #The acceleration one body applies to another is given by
    #the equation 'a = G*M/(r^2). But of course we just ignore the Gravitational constant

    #'i' is the Body that we are calculating its accel and vel for
    for i in range(len(self.objects)):

      #'a' corresponds to a sum-type variable to calculate the new acceleration
      a = Vec3(0,0,0)

      #'j' is the Body which force interaction with 'i' we are going to calculate
      for j in range(len(self.objects)):
    
        #A Body doesn't interact with itself
        if i != j:
          #Gets the vector from the 'i' object to the 'j' object and normalizes it
          vec = self.objects[j].node.getPos() - self.objects[i].node.getPos()
          vec.normalize()

          #Multiplies it by the 'j' object's mass ('M' in the equation)
          vec *= self.objects[j].mass

          #Divides it by the square of the distance between the two bodies ('r^2' in the equation)
          vec /= (self.objects[i].node.getPos() - self.objects[j].node.getPos()).lengthSquared()
          a += vec
      #'i' object's velocity is added by 'a'
      self.objects[i].vel = self.objects[i].vel + a
      #And its acceleration is now 'a'
      self.objects[i].acel = a

    #Changes the object's position accordingly. The mass restriction is because black holes and
    #while holes aren't supposed to move at all.
    for i in range(len(self.objects)):
      if self.objects[i].mass <= 1 and self.objects[i].mass > 0:
        self.objects[i].node.setPos(self.objects[i].node.getPos() + self.objects[i].vel)


    #Draw red lines connection planets according to the caution level which can be changed
    #with the keyboard. This ranges from drawing no lines at all to drawing lines connecting
    #every planet.
    #Caution level -1: shows lines connecting all planets, one with each other;
    #Caution level 0: turns the lines of connection off
    #Caution level 1: 
    #Caution level 2: 
    self.lines.reset()
    if self.caution > 0:
      lines = []
      for i in range(len(self.objects)):
        pf = Point3(100,100,100)
        df = 100
        for j in range(len(self.objects)):
          if i != j:
            d = (self.objects[i].node.getPos() - self.objects[j].node.getPos()).length()
            if d < df:
              pf = (self.objects[j].node.getPos())
              df = d
        if self.caution == 2:
          lines.append((self.objects[i].node.getPos(),pf))
        if (self.objects[i].node.getPos() - pf).length() < 20 and self.caution == 1:
          lines.append((self.objects[i].node.getPos(),pf))
        self.lines.drawLines(lines)
        self.lines.create()
    if self.caution == -1:
      lines = []
      for i in range(len(self.objects)):
        for j in range(len(self.objects)):
          lines.append((self.objects[i].node.getPos(),self.objects[j].node.getPos()))
        self.lines.drawLines(lines)
        self.lines.create()


    return task.again


  def traverseTask(self,task):
    #This function is responsible for treating collisions

    #Puts every collision in the collisionHandler.getEntry() list
    self.collisionHandler.sortEntries()
    
    for i in range(self.collisionHandler.getNumEntries()):
      entry = self.collisionHandler.getEntry(i)
      for j in range(len(self.objects)):
        #Compares the collided object's mass with every body mass in order to find which Body object collided
        if entry.getIntoNodePath().getParent().getPos() == self.objects[j].node.getPos() and self.objects[j].mass <= 1 and self.objects[j].mass > 0:
          #Deletes the Body object from the main objects array, so it won't interact with other bodies anymore
          self.objects.pop(j)
          #Detaches its pandaNode so it won't be renderized anymore.
          entry.getIntoNodePath().getParent().detachNode()
          break
      #print "Collision: into",entry.getIntoNode().getName()
    return task.again


  def keyboardPress(self,status):
    #Callback for key presses
    #For now this only changes the caution level
    if status == "1":
      self.caution = 0
    elif status == "2":
      self.caution = 1
    elif status == "3":
      self.caution = 2
    elif status == "'":
      self.caution = -1

  def mouseClick(self,status):
    #This functions is the callback for a mouse click
    #All major skills (hazards) are going to be modelated here

    if base.mouseWatcherNode.hasMouse():
      #First we get the mouse position on the screen during the click
      mpos = base.mouseWatcherNode.getMouse()
      
      #Initializes three variables that are going to be filled by panda functions
      pos3d = Point3() 
      nearPoint = Point3() 
      farPoint = Point3()

      #Makes an extrusion from the camera lens to the mouse position (on the 2d screen)
      #This function fills nearPoint and farPoint with the near and far 3d positions
      #of frustrum.
      base.camLens.extrude(mpos, nearPoint, farPoint)

      #Fills pos3d with the 3d position of picked position
      #This is done by checking the intersection between the line
      #defined by the nearPoint and farPoint, and the plane itself.
      if self.plane.intersectsLine(pos3d, 
                                   render.getRelativePoint(camera, nearPoint), 
                                   render.getRelativePoint(camera, farPoint)):

        #This creates a black hole. Same procedure as planets and sun creation.
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

        #This creates a while hole. Nothing more than a Body with negative mass.
        if status == "down2":
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
    #This function just makes every Body rotate with a panda Interval function
    self.day_period_object = [0]*(len(self.objects)-1)
    self.sun_period = self.objects[0].node.hprInterval(20, Vec3(360, 0, 0))
    self.sun_period.loop()
    for i in range(len(self.objects)-1):
      self.day_period_object[i] = self.objects[i+1].node.hprInterval(self.objects[i].mass*1500, Vec3(360, 0, 0))
      self.day_period_object[i].loop()


  
w = World()
run()
