import direct.directbase.DirectStart
from direct.showbase.ShowBase import ShowBase
from direct.gui.DirectGui import *
from panda3d.core import Vec3, Vec4, Point3, Point4
from direct.showbase.DirectObject import DirectObject
import random
import sys
import math
from direct.directtools.DirectGeometry import LineNodePath
from direct.gui.OnscreenText import OnscreenText
from pandac.PandaModules import CollisionHandlerQueue, CollisionNode, CollisionSphere, CollisionTraverser, BitMask32, CollisionRay
from direct.showbase.ShowBase import Plane, ShowBase, Vec3, Point3, CardMaker 
from direct.directbase.DirectStart import *
from pandac.PandaModules import *


#VERSION 0.5.0
#THIRD VERSION BUMP FOR ANY CHANGE
#SECOND VERSION BUMP IF A MAJOR FEATURE HAS BEEN DONE WITH
#FIRST VERSION BUMP IF THE GAME IS RC


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
    #Creates the main region which displays the solar system itself
    #Also creates a new mouseWatcherNode so mouse picking works
    #according to the region clicked during the mouse callback
    self.mainRegion = base.cam.node().getDisplayRegion(0)
    self.mainRegion.setDimensions(0,0.8,0,1)
    base.mouseWatcherNode.setDisplayRegion(self.mainRegion)
    base.setBackgroundColor(0, 0, 0)
    
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

    base.setFrameRateMeter(True)
    
    #Same procedure as above, but this is for the menu
    self.menuRegion = base.win.makeDisplayRegion(0.8,1,0,1)
    self.menuRegion.setSort(0)
    myCamera2d = NodePath(Camera('myCam2d'))
    lens = OrthographicLens()
    lens.setFilmSize(2, 2)
    lens.setNearFar(-1000, 1000)
    myCamera2d.node().setLens(lens)
    self.myRender2d = NodePath('myRender2d')
    self.myRender2d.setDepthTest(False)
    self.myRender2d.setDepthWrite(False)
    myCamera2d.reparentTo(self.myRender2d)
    self.menuRegion.setCamera(myCamera2d)
    aspectRatio = base.getAspectRatio()
    myAspect2d = self.myRender2d.attachNewNode(PGTop('myAspect2d'))
    myAspect2d.setScale(1.0 / aspectRatio, 1.0, 1.0)
    myAspect2d.node().setMouseWatcher(base.mouseWatcherNode)
    imageObject = OnscreenImage(image = 'models/menu.jpg', scale =  (1,1,1), parent = self.myRender2d)
    
    #Creates a line connecting planets when these are close enough to satisfy self.orbitscale.
    #Different values of self.caution define how far lines start to appear,
    #but will make more sense by the time others difficult levels get implemented.
    self.caution = 0
    self.lines = LineNodePath(parent = render, thickness = 3.0, colorVec = Vec4(1, 0, 0, 1))
    self.orbitlines = LineSegs()
    self.orbitlines.setThickness(1)
    self.orbitlines.setColor(Vec4(0,1,0,1))
    self.orbitsegnode = NodePath("")
    
    self.sizescale = 1.6
    self.orbitscale = 10

    #How many times the prediction loop will be ran
    self.pred = 30
    
    #Define game pace
    self.pace = 1
    
    #Objects is the main array that keeps trace of all the Body type objects
    self.objects = []

    #Initialize parameter for the meteor creation routines
    self.meteorcreated = False
    
    #Unimportant parameters
    self.yearscale = 60
    self.dayscale = self.yearscale / 365.0 * 5
    self.sizescale = 1.6
    self.orbitscale = 10

    #n defines the number of planets to be created
    self.n = 4

    #Creates the handler of collisions and makes it be referenced by self.collisionHandler
    base.cTrav=CollisionTraverser()
    self.collisionHandler = CollisionHandlerQueue()

    #Selection of callback functions
    DO=DirectObject()
    DO.accept('a', self.keyboardPress, ['a'])
    DO.accept('s', self.keyboardPress, ['s'])
    DO.accept('d', self.keyboardPress, ['d'])
    DO.accept('w', self.keyboardPress, ['w'])
    
    #Creation of the plane defined by the solar system (normal (0,0,1) and point(0,0,0))
    self.plane = Plane(Vec3(0, 0, 1), Point3(0, 0, 0))

    #Tries to load the soundtrack
    try:
      mySound = base.loader.loadSfx("m2.mp3")
      mySound.play()
    except: pass

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

    
  def keyboardPress(self,status):
    #Callback for key presses
    #For now this only changes the caution level
    if status == "a": self.caution = 0
    elif status == "s": self.caution = 1
    elif status == "d": self.caution = 2
    elif status == "w": self.caution = -1
    

  def loadPlanets(self):
    #This function is responsible for creating the bodies upon the start of the game

    #Loads the model for the sky (big ball surrounding the system)
    #The model in question is an inverted sphere (sphere with a negative normal vector)
    #This is used since we want to see the inside of the sphere, and also only treat
    #collisions when other objects leave the sphere
    self.sky = loader.loadModel("models/solar_sky_sphere")
    self.sky.setName("sky")
    
    #Reparenting to 'render' is makes the model visible. Otherwise it wouldn't be renderized.
    self.sky.reparentTo(render)

    #Sets the size of the sky sphere
    self.sky.setScale(150)

    #Makes it just a black sphere if the texture is not found , otherwise loads it.
    try:
      self.sky_tex = loader.loadTexture("models/s.jpg")
      self.sky.setTexture(self.sky_tex, 1)
    except:
      self.sky.setColor(0,0,0,0)
    self.skyCollider = self.sky.attachNewNode(CollisionNode('skynode'))
    self.skyCollider.node().addSolid(CollisionInvSphere(0, 0, 0, 1))
    base.cTrav.addCollider(self.skyCollider, self.collisionHandler)


    #Exactly the same procedure as the sky sphere creation
    #The only difference is that a common sphere is used as the model
    self.sun = loader.loadModel("models/planet_sphere")
    self.sun.setName("sun")
    try:
      self.sun_tex = loader.loadTexture("models/s%s.jpg"%(int(random.random()*6)))
      self.sun.setTexture(self.sun_tex, 1)
    except: pass
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
      self.planet.setName("planet%d"%i)
      try:
        self.planet_tex = loader.loadTexture("models/p%s.jpg"%(int(random.random()*9)))
        self.planet.setTexture(self.planet_tex, 1)
      except: pass
      self.planet.reparentTo(render)
      
      #Two seeds are created randomly, one for the X pos and size, the other for the Y pos
      seed = random.random()
      seed2 = random.random()
      self.planet.setPos(Point3((i+1) * self.orbitscale, 0, 0))
      #self.planet.setPos( (10*(seed-0.5) * self.orbitscale, 10*(seed2-0.5) * self.orbitscale, 0))
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
      if i != 0 and self.objects[i].node.getName() != "dummy":
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
          
      #Non-moving objects shouldn't have their speeds or accelerations changed
      if 0 < self.objects[i].mass < 1:
        #'i' object's velocity is added by 'a'
        self.objects[i].vel = self.objects[i].vel + a * self.pace
        #And its acceleration is now 'a'
        self.objects[i].acel = a
        
    #Changes the object's position accordingly. The mass restriction is because black holes,
    #while holes and worm holes aren't supposed to move at all.
    for i in range(len(self.objects)):
      if 0 < self.objects[i].mass < 1:
        self.objects[i].node.setPos(self.objects[i].node.getPos() + self.objects[i].vel *self.pace)

        
    #Does the previous calculation 30 times ahead, so the player can have a prediction on
    #the path each planet will follow.
    for i in self.objects:
      i.predPos = [i.node.getPos()]
      i.predVel = i.vel
      i.predAcel = i.acel
      i.node.clearColor()
      i.danger = False
    for k in range(self.pred):
      for i in self.objects:
        a = Vec3(0,0,0)
        for j in self.objects:
          if i != j and j.node.getName() not in "blackhole,whitehole,randombh,randomwh":
            vec = j.predPos[-1] - i.predPos[-1]
            vec.normalize()
            vec *= j.mass
            vec /= (i.predPos[-1] - j.predPos[-1]).lengthSquared()
            a += vec
        i.predVel = i.predVel + a * 5
        i.predAcel = a
        for j in self.objects:
          if i != j:
            ki = min(k,len(i.predPos)-1)
            kj = min(k,len(j.predPos)-1)
            if (i.predPos[ki] - j.predPos[kj]).length() < (j.node.getScale()[0] + i.node.getScale()[0]):
              j.node.setColor(Vec4(1,0,0,1))
              j.danger = True
        if i.danger and i.node.getName() != "activedummy":
          i.predPos.append(i.predPos[-1])
        elif (0 < i.mass < 1 or i.node.getName() == "activedummy"): 
          i.predPos.append(i.predPos[-1] + i.predVel * 5)
          

    #Draw lines showing the prediction of each planet's path
    #This is done by the use of line segments with increasing alpha
    self.orbitsegnode.removeNode()
    self.orbitlines.reset()
    for i in range(len(self.objects)):
      if 0 < self.objects[i].mass < 1  or self.objects[i].node.getName() == "activedummy":
        self.orbitlines.moveTo(self.objects[i].predPos[0])
        for j in range(1,self.pred):
          self.orbitlines.drawTo(self.objects[i].predPos[j+1])
    self.orbitsegnode = render.attachNewNode(self.orbitlines.create())
    self.orbitsegnode.setTransparency(True)
    segs = 0
    for i in range(len(self.objects)):
      if 0 < self.objects[i].mass < 1  or self.objects[i].node.getName() == "activedummy":
        alpha = 0
        for j in range(self.pred):
          self.orbitlines.setVertexColor(segs*self.pred+j,0.13,0.41,0.55,1-alpha)
          alpha += 0.02
        segs += 1


    """#Draw red lines connection planets according to the caution level which can be changed
    #with the keyboard. This ranges from drawing no lines at all to drawing lines connecting
    #every planet.
    #Caution level -1: shows lines connecting all planets, one with each other;
    #Caution level 0: turns the lines of connection off
    #Caution level 1: shows lines connecting planets when the distance is less than 20
    #Caution level 2: shows lines connection every planet with its nearest neighbour
    lines = []
    if self.caution > 0:
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
    if self.caution == -1:
      for i in range(len(self.objects)):
        for j in range(len(self.objects)):
          lines.append((self.objects[i].node.getPos(),self.objects[j].node.getPos()))
    self.lines.drawLines(lines)
    self.lines.create()"""
    return task.again


  def traverseTask(self,task):
    #This function is responsible for treating collisions

    #Puts every collision in the collisionHandler.getEntry() list
    self.collisionHandler.sortEntries()

    for i in range(self.collisionHandler.getNumEntries()):
      entry = self.collisionHandler.getEntry(i)
      fromname = entry.getFromNodePath().getName()
      intoname = entry.getIntoNodePath().getName()
      anyname = fromname + intoname
      if  "mtnode" in anyname:
        self.meteorcreated = False
      if intoname in "skynode,sunnode,bhnode,whnode,holenode" and fromname not in "skynode,sunnode,bhnode,whnode,holenode":
        for j in range(len(self.objects)):
          if entry.getFromNodePath().getParent().getName() == self.objects[j].node.getName():
            self.objects.pop(j)
            entry.getFromNodePath().getParent().detachNode()
            break
      if "planetnode" in fromname and "planetnode" in intoname:
        for j in range(len(self.objects)):
          if entry.getFromNodePath().getParent().getName() == self.objects[j].node.getName():
            self.objects.pop(j)
            entry.getFromNodePath().getParent().detachNode()
            break
        for j in range(len(self.objects)):
          if entry.getIntoNodePath().getParent().getName() == self.objects[j].node.getName():
            self.objects.pop(j)
            entry.getIntoNodePath().getParent().detachNode()
            break
      if "mtnode" in fromname and "planetnode" in intoname:
        mtvel = Vec3(0,0,0)
        for j in range(len(self.objects)):
          if entry.getFromNodePath().getParent().getName() == self.objects[j].node.getName():
            mt = self.objects.pop(j)
            mtvel = mt.vel*mt.mass
            entry.getFromNodePath().getParent().detachNode()
            break
        for j in range(len(self.objects)):
          if entry.getIntoNodePath().getParent().getName() == self.objects[j].node.getName():
            self.objects[j].vel += mtvel/self.objects[j].mass
            break
    
    return task.again


  def rotatePlanets(self):
    #This function just makes every Body rotate with a panda Interval function
    self.day_period_object = [0]*(len(self.objects)-1)
    self.sun_period = self.objects[0].node.hprInterval(20, Vec3(360, 0, 0))
    self.sun_period.loop()
    for i in range(len(self.objects)-1):
      self.day_period_object[i] = self.objects[i+1].node.hprInterval(self.objects[i].mass*1500, Vec3(360, 0, 0))
      self.day_period_object[i].loop()
      
  def vanishNode(self, name):
    #End with a black or white hole creation
    for i in range(len(self.objects)):
      if self.objects[i].node.getName() == name:
        self.objects[i].node.detachNode()
        self.objects.pop(i)
        break
        
      
class CameraHandler(DirectObject):
  '''Defines and controls the camera'''
  def   __init__(self): 
    base.disableMouse() 
    self.setupVars() 
    self.setupCamera() 
    self.setupInput() 
    self.setupTasks() 
       
  def setupVars(self):
    '''Initialize vars values'''
    self.initPitch = 10         #Anchor initial pitch (camera will start slighly from above)
    self.initZoom = 250         #Camera's initial distance from anchor
    self.zoomInLimit = 40       #Camera's minimum distance from anchor
    self.zoomOutLimit = 600     #Camera's maximum distance from anchor
    self.orbit = None 
    
  def setupCamera(self):
    '''Define an anchor node which camera will follow
       set camera and achor positions
    '''
    self.camAnchor = render.attachNewNode("Cam Anchor") 
    base.camera.reparentTo(self.camAnchor)
    base.camera.setPos(0, -self.initZoom, 0) 
    base.camera.lookAt(self.camAnchor)
    self.camAnchor.setP(-self.initPitch)
       
  def setupInput(self):
    '''Define mouse callback functions'''
    #Zoom functions
    self.accept("wheel_up", self.setZoom, ['up']) 
    self.accept("wheel_down", self.setZoom, ['down']) 
    #Orbiting functions
    self.accept("mouse3", self.setOrbit, [True])
    self.accept("mouse3-up", self.setOrbit, [False]) 
    
  def setupTasks(self):
    '''Add new task to be called every frame for camera orbiting'''
    taskMgr.add(self.cameraOrbit, "Camera Orbit")

  def setZoom(self, zoom):
    '''Method that zoom ir or out the camera'''
    y = base.camera.getY()  #Get camera position
 
    #This block smooths the zoom movement by varying less if camera is closer
    if y > -60.0:
      delta = 1
    elif y > -90:
      delta = 2
    elif y > -120:
      delta = 4
    elif y > -150:
      delta = 6
    elif y > -180:
      delta = 8
    elif y > -250.0:
      delta = 12
    else:
      delta = 20
      
    if (zoom == 'up'):
      newY = y + delta
      #Verify if the new position respects the zoom in limit
      if newY > -self.zoomInLimit: newY = -self.zoomInLimit
    else:
      newY = base.camera.getY() - delta
      #Verify if the new position respects the zoom in limit
      if newY < -self.zoomOutLimit: newY = -self.zoomOutLimit
      
    base.camera.setY(newY)  #Set new position
    
  def setOrbit(self, orbit):
    '''Get the mouse position when clicked'''
    if(orbit == True):
      #Get windows size
      props = base.win.getProperties() 
      winX = props.getXSize()
      winY = props.getYSize()
      if base.mouseWatcherNode.hasMouse():
        #Get mouse position when clicked
        mX = base.mouseWatcherNode.getMouseX() 
        mY = base.mouseWatcherNode.getMouseY()
        #Get absolute mouse position on the screen
        mPX = winX * ((mX+1)/2)
        mPY = winY * ((-mY+1)/2) 
      self.orbit = [[mX, mY], [mPX, mPY]]
    else: 
      self.orbit = None
    
  def cameraOrbit(self, task):
    '''Task to move the camera around the anchor each frame'''
    if(self.orbit != None): 
      if base.mouseWatcherNode.hasMouse(): 
        
        #Get current mouse position
        mpos = base.mouseWatcherNode.getMouse()
        
        #Calculates the variation of the movement
        deltaH = 90 * (mpos[0] - self.orbit[0][0]) 
        deltaP = 90 * (mpos[1] - self.orbit[0][1]) 
        limit = .5 
        
        #Set the new mouse position for next task
        self.orbit[0] = [mpos[0], mpos[1]]
        
        # These two blocks verify whether the variation is negligible and smooths the movement
        if(-limit < deltaH and deltaH < limit): 
          deltaH = 0 
        elif(deltaH > 0): 
          deltaH - limit 
        elif(deltaH < 0): 
          deltaH + limit 
                
        if(-limit < deltaP and deltaP < limit): 
          deltaP = 0
        elif(deltaP > 0): 
          deltaP - limit
        elif(deltaP < 0): 
          deltaP + limit 

        #Set new heading and pitch for the anchor
        newH = (self.camAnchor.getH() + -deltaH) 
        newP = (self.camAnchor.getP() + deltaP)
        #Don't let the camera pitch go beyond 90 degrees
        if(newP < -90): newP = -90 
        if(newP > 0): newP = 0
        
        #Set the pitch
        self.camAnchor.setHpr(newH, newP, 0)             
          
    return task.cont

    
class ResourceHandler:
  #Control the use of recourses
  #They are increased with time in each frame and are decresead by using skills
  def __init__(self):
    self.res = 2000.0     #Initial quantity of resource
    self.maxres = 5000.0 #Maximum amount of resource
    self.inc = 0.1      #Defines resources increased each frame
    
    #Print an onscreen text with the resources
    self.resourceText = OnscreenText(text = 'PP: ' + str(int(self.res)), pos = (0, 0.3), scale = (0.3,0.1), fg = (255,255,255,200), parent = World.myRender2d)
    
    #Add a task for resource related functions
    taskMgr.add(self.resourceTask, "Resource Task")
    
  def resourceTask (self, task):
    #Task called each frame for functions related to resources
    self.gainRes(self.inc)   #Inscrease resources each frame
    
    self.resourceText.destroy()
    self.resourceText = OnscreenText(text = 'PP: ' + str(int(self.res)), pos = (0, 0.3), scale = (0.3,0.1), fg = (255,255,255,200), parent = World.myRender2d)
    
    return task.cont

  def checkResource (self, amount):
    #Check if there is at least a quantity amount of resources
    if self.res >= amount:
      return True
    else:
      return False
  
  def spendRes (self, delta):
    #Decrease a certain amount of resources
    if self.res - delta >= 0:
      self.res -= delta
    else:
      self.res = 0
    
  def gainRes (self, delta):
    #Increase a certain amount of resources
    if self.res + delta <= self.maxres:
      self.res += delta
    else:
      self.res = self.maxres
    

class SkillHandler (DirectObject):
  #Class that take care of callbacks, modeling and the control of resources related to the use of skills.
  def __init__(self):
    #Initialize the resourse handler
    self.resource = ResourceHandler()
    
    #Defines the cost of resources needed for each skill in a dictionary
    self.cost = {"blackhole" : 1, "whitehole" : 1, "meteor" : 10, "wormhole" : 10, "slowmotion" : 0.5}  #{blackhole, whitehole, meteor, wormhole, slow-motion}
    self.selectedSkill = "blackhole"   #set the default selected skill
    self.activeSkill = ""       #set the skill being used as null
    self.slow = False           #set the slow motion flag to false (disabled)
   
    #Initialize wormholes parameters
    self.holes = []     #store the wormholes
    self.nholes = 2     #defines the max number of wormholes
 
    #Initialize parameters for the meteor creation routines
    self.meteorline = LineNodePath(parent = render, thickness = 1, colorVec = Vec4(1, 0, 0, 1))
    self.createMeteorPath()
   
    #Mouse and keyboard callbacks
    self.setupInput()
    self.setupTasks()
    
    
  def setupTasks(self):
    #Add new tasks to be called every frame
    taskMgr.add(self.drawMeteorPath, "Meteor Path")
    taskMgr.add(self.slowMotion, "Slow Motion")
    taskMgr.add(self.useResource, "Use Resource")
    
    
  def setupInput(self):
    #Defines callback functions
    self.accept('mouse1', self.leftMouseClick, ['down'])  #use active skill
    self.accept('mouse1-up', self.leftMouseClick, ['up']) #stop using active skill
    self.accept('z', self.keyboardPress, ['z']) #select Black Hole
    self.accept('x', self.keyboardPress, ['x']) #select White Hole
    self.accept('c', self.keyboardPress, ['c']) #select Meteor
    self.accept('v', self.keyboardPress, ['v']) #select Wormhole
    self.accept('space', self.keyboardPress, ['space-down'])  #select slow-down
    self.accept('space-up', self.keyboardPress, ['space-up']) #release slow-down
    
    
  def keyboardPress(self, status):
    #Callback for key presses
    #Sets the skills parameters
    if status == "z": self.selectedSkill = "blackhole"
    elif status == "x": self.selectedSkill = "whitehole"
    elif status == "c": self.selectedSkill = "meteor"
    elif status == "v": self.selectedSkill = "wormhole"
    elif status == "space-down" and self.resource.checkResource(self.cost["slowmotion"]): #Check if there are enough resources for the skill
      self.slow = True
    elif status == "space-up": self.slow = False
 
 
  def useResource (self, task):
    #Decrease resources continually each frame as long as a certain skill is active
    #Only use resources when determined skills are active
    if self.activeSkill in ["blackhole","whitehole"]:
      if self.resource.checkResource(self.cost[self.activeSkill]):
        #Spend resources needed to perform the skill
        self.resource.spendRes(self.cost[self.activeSkill])
      else: 
        #If there are no resources end the skill use
        World.vanishNode(self.activeSkill)
        self.activeSkill = ""
    return task.again
   
 
  def leftMouseClick(self, status):
    #This functions is the callback for a mouse click
    #All major skills (hazards) are going to be modelated here
    #Check if mouse is pressed down and if there are enough resources to use the selected skill
    if base.mouseWatcherNode.hasMouse() and status == "down" and self.resource.checkResource(self.cost[self.selectedSkill]):
      #Get the 3d position of the mouse click
      pos3d = self.getPos3d(base.mouseWatcherNode.getMouse())
      
      if pos3d:
        if self.selectedSkill == "blackhole":
          #Creates a black hole.
          self.activeSkill = self.selectedSkill
          self.createBlackHole(pos3d, self.activeSkill)
          
        elif self.selectedSkill == "whitehole":
          #Creates a white hole.
          self.activeSkill = self.selectedSkill
          self.createWhiteHole(pos3d, self.activeSkill)
          
        elif self.selectedSkill == "meteor" and not World.meteorcreated and self.holes:
          #Create the meteor path prediction
          self.activeSkill = self.selectedSkill
          self.setupMeteorPath(pos3d)
          
        elif self.selectedSkill == "wormhole" and self.nholes > 0:
          #Creates a worm hole.
          self.createWormHole(pos3d, self.selectedSkill)
          self.resource.spendRes(self.cost[self.selectedSkill])
          
    elif base.mouseWatcherNode.hasMouse() and status == "up":
      
      if self.activeSkill in ["blackhole", "whitehole"]:
        #Destroy the black or white hole
        World.vanishNode(self.activeSkill)
        self.activeSkill = ""
        
      elif self.activeSkill == "meteor" and not World.meteorcreated:
        #Create meteor.
        self.createMeteor(self.meteorvector[0], self.meteorvector[1], self.activeSkill)
        World.meteorcreated = True
        self.resource.spendRes(self.cost[self.activeSkill])
        self.activeSkill = ""

        
  def getPos3d(self, mpos):
    #Receives mouse position on screen and return the equivalent 3d position in the game world plane
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
    if World.plane.intersectsLine(pos3d, 
                                 render.getRelativePoint(camera, nearPoint), 
                                 render.getRelativePoint(camera, farPoint)):
      return pos3d
    else:
      return False
        
        
  def slowMotion (self, task):
    #Slows the time or turns it a little back to normal if the player is holding space
    if self.slow == True and World.pace > 0.2:
      self.resource.spendRes(self.cost["slowmotion"])
      World.pace = World.pace - 0.02
    elif World.pace < 1:
      World.pace += 0.02
    return task.again
        
        
  def createMeteorPath(self):
    #Creates a dummy node to predict the path of a to-be-created meteor
    self.dummy = NodePath("dummy")
    self.dummy.reparentTo(render)
    self.dummy.setPos(Point3(100,100,0))
    self.dummy = Body(self.dummy,0,Vec3(0,0,0),Vec3(0,0,0))
    World.objects.append(self.dummy)
    
    
  def setupMeteorPath(self, pos):
    #Use the dummy node created for meteor prediction and configure it to the actual position and wormhole
    self.dummy.node.setName("activedummy")
    start = None
    for i in self.holes:
      if not start: start = i.getPos()
      elif (pos - i.getPos()).length() < (pos - start).length(): start = i.getPos()
    self.dummy.node.setPos(start+Vec3(0.1,0,0))
    self.meteorvector = [start,pos]
    self.dummy.vel = (self.meteorvector[0]-self.meteorvector[1])/30.0

      
  def drawMeteorPath(self, task):
    #Draw a line to indicate the direction and speed of the meteor creation
    self.meteorline.reset()
    meteorline = []
    if self.activeSkill == "meteor" and base.mouseWatcherNode.hasMouse():
      pos3d = self.getPos3d(base.mouseWatcherNode.getMouse())
      if pos3d:
        self.meteorvector[1] = pos3d
        meteorline.append((self.meteorvector[0],self.meteorvector[1]))
        self.dummy.vel = (self.meteorvector[0]-self.meteorvector[1])/30.0
        self.meteorline.drawLines(meteorline)
        self.meteorline.create()
    return task.again

        
  def createMeteor(self, pos0, pos1, name):
    #Create a meteor object in the game world
    self.dummy.node.setName("dummy")
    meteor = loader.loadModel("models/planet_sphere")
    meteor.setName(name)
    try:
      meteor_tex = loader.loadTexture("models/bh.jpg")
      meteor.setTexture(meteor_tex, 1)
    except: pass
    meteor.reparentTo(render)
    auxvec = pos0 - pos1
    auxvec.normalize()
    meteor.setPos(pos0 + auxvec)
    meteor.setScale(0.2)
    meteorCollider = meteor.attachNewNode(CollisionNode('mtnode'))
    meteorCollider.node().addSolid(CollisionSphere(0, 0, 0, 1))
    base.cTrav.addCollider(meteorCollider, World.collisionHandler)
    World.objects.append(Body(meteor,0.001,(pos0 - pos1)/30.0,Vec3(0,0,0)))
  
  
  def createBlackHole(self, pos, name):
    #This creates a black hole. Same procedure as planets and sun creation.
    blackhole = loader.loadModel("models/planet_sphere")
    blackhole.setName(name)
    try:
      blackhole_tex = loader.loadTexture("models/bh.jpg")
      blackhole.setTexture(blackhole_tex, 1)
    except: pass
    blackhole.reparentTo(render)
    blackhole.setPos(pos)
    blackhole.setScale(2)
    blackholeCollider = blackhole.attachNewNode(CollisionNode('bhnode'))
    blackholeCollider.node().addSolid(CollisionSphere(0, 0, 0, 1))
    base.cTrav.addCollider(blackholeCollider, World.collisionHandler)
    World.objects.append(Body(blackhole,3,Vec3(0,0,0),Vec3(0,0,0)))
      
  
  def createWhiteHole(self, pos, name):
    #Creates a white hole on the game world.
    whitehole = loader.loadModel("models/planet_sphere")
    whitehole.setName(name)
    try:
      self.whitehole_tex = loader.loadTexture("models/bh.jpg")
      self.whitehole.setTexture(whitehole_tex, 1)
    except: pass
    whitehole.reparentTo(render)
    whitehole.setPos(pos)
    whitehole.setScale(2)
    whiteholeCollider = whitehole.attachNewNode(CollisionNode('whnode'))
    whiteholeCollider.node().addSolid(CollisionSphere(0, 0, 0, 1))
    base.cTrav.addCollider(whiteholeCollider, World.collisionHandler)
    World.objects.append(Body(whitehole,-1,Vec3(0,0,0),Vec3(0,0,0)))

    
  def createWormHole(self, pos, name):
    #Creates a worm hole.
    #Meteors can only be generated throw wormholes
    self.nholes -= 1
    wormhole = loader.loadModel("models/planet_sphere")
    wormhole.setName(name)
    wormhole.reparentTo(render)
    wormhole.setPos(pos)
    wormhole.setScale(0.5)
    wormholeCollider = wormhole.attachNewNode(CollisionNode('holenode'))
    wormholeCollider.node().addSolid(CollisionSphere(0, 0, 0, 1))
    base.cTrav.addCollider(wormholeCollider, World.collisionHandler)
    World.objects.append(Body(wormhole,0,Vec3(0,0,0),Vec3(0,0,0)))
    self.holes.append(wormhole)

    
class RandomHazardsHandler:
  def __init__ (self):
    self.randomHazard = ""    #the active random hazard
    self.freq = random.randint(100,200)    #ramdonly generated number of frames before another hazard
    self.duration = 0        #the duration of a random hazard
    self.hazards = ["randombh", "randomwh", "randommt"]
    taskMgr.add(self.randomHazardTask, "Random Hazard Task")

  def randomHazardGenerator(self):
    #Called every time a random Hazard is going to happen
    self.randomHazard = random.choice(self.hazards)   #get a random skill from the list of skills

    if self.randomHazard in ["randombh", "randomwh"]:
      self.duration = int(random.gauss(130, 40))
      radius = random.randint(100,150)
      angle = random.random()*2*math.pi
      vx = radius*math.sin(angle)
      vy = radius*math.cos(angle)
      pos = Point3(vx,vy,0)

      if self.randomHazard == "randombh":
        Skills.createBlackHole(pos, self.randomHazard)
        
      elif self.randomHazard == "randomwh":
        Skills.createWhiteHole(pos, self.randomHazard)
     
    else:
      angle = random.random()*2*math.pi
      start = Point3(-150*math.cos(angle),-150*math.sin(angle),0)
      endx = start[0]-10*math.cos(angle)+random.random()*3
      endy = start[1]-10*math.sin(angle)+random.random()*3
      end = Point3(endx,endy,0)
      Skills.createMeteor(start, end, self.randomHazard)
      self.randomHazard = ""
        
        
  def randomHazardTask(self, task):
    if not self.randomHazard:   #check if there isn't any active hazard   
      self.freq -= 1            #countdown the number of frames before a hazard
      if self.freq == 0:
          self.randomHazardGenerator()          #generate a random hazard
          self.freq = random.randint(200,400)   #ramdonly generated number of frames before another hazard
    else:
      if self.randomHazard in ["randombh", "randomwh"]:
        self.duration -= 1
        if self.duration == 0:
            World.vanishNode(self.randomHazard)
            self.randomHazard = ""
    return task.again
    

World = World()
Skills = SkillHandler()
Camera = CameraHandler()
RandomHazards = RandomHazardsHandler()
run()
