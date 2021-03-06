####HarvesterClient.py
## THis is the client portion of the harvester
import sys
import HarvesterLog
from gevent import monkey
from gevent import Greenlet
monkey.patch_all()
from gevent import socket
import gevent
from gevent import pool
import pickle
from termcolor import colored
import MySQLdb
import Queue
import datetime
import time
import twiAuth
import glob
import twython
import pdb

class HarvesterClient:
	def log(self, message):
		self.logger.log(message)
		self.logger2.log(message)
		
	def log2(self, message):
		self.logger2.log(message)		
		
	def receiveWelcomeMessage(self, mysocket):
		socketFileHandle = mysocket.makefile()
		readaline = socketFileHandle.readline()
		print colored(readaline, "red")
		
	#Server is sending a client a list of clients this client should connect to
	def updateClientsList(self, mysocket):
		socket.wait_read(mysocket.fileno())
		socketFileHandle = mysocket.makefile()
		readaline = socketFileHandle.read()
		server_clients = pickle.loads(readaline)	
		self.peerlist.append(server_clients)
	
		
	#The socket should be the command socket
	def connectToServer(self, ip):
		self.log("Connecting to server on " + str(ip))
		mysocket = socket.create_connection((ip, self.server_port), 20)
		self.receiveWelcomeMessage(mysocket)
		self.updateClientsList(mysocket)
		return mysocket
	
	#TODO: When new clients join, server pings client and checks the client version. 
		
	def validateIP(self, ip):
		from IPy import IP
		if ip == "localhost":
			ip = "0.0.0.0"
		try:
			IP(ip)
			self.log("IP: " + str(ip) + "is valid, connecting now")
		except ValueError:
			print ip, "is not a valid IP address"
			sys.exit()
			
	def spawnStreamCapture(self):
		#TODO: Write client code to get client commands
		pass
	
	def connectToOtherClients(self, mysocket):
		if len(self.peerlist) < 1:
			print "I'm the first client"
		else:
			print "Trying to connect to other clients, listed here: ", self.peerlist
			#TODO: figure out if I need to open sockets with other clients, or just use the chat channel. 

	def parseIncoming(self, *args, **kwargs):
		print args, kwargs

	def listenOnSocket(self):
		#TODO: Listen to other clients connection attempts
		while 1:
			print "waiting for server or clients to contact..."
			socketfileno = self.chatComm.fileno()
			gevent.socket.wait_read(socketfileno, event=self.parseIncoming)
	
	def testDBConn(self, conn):
		cursor = conn.cursor()
		try: 
			#Test the connection
			cursor.execute ("SELECT VERSION()")
			print colored("Harvester SQL Database connected", "green")
			row = cursor.fetchone()
			print "\t mysql database server version:", row[0]		
		except ValueError:
			return ValueError
		
	
	def connectToDB(self):
		conn = MySQLdb.connect(host = "harvesterSQL2.cloudapp.net",
                           user = "client",
                           passwd = "pass4Harvester",
                           db = "harvestDB")		
		return conn;
	
	def FolderGrabber(self):
		print "\tSpawned a ID grabber to grab IDs in the neighbouring folders"
		IDfiles = glob.glob('*.txt')
		moreFiles = glob.glob('IDfiles/*')
		IDfiles = IDfiles + moreFiles
		dbconn = self.connectToDB()
		cursor = dbconn.cursor()
		realtime = "2013-11-18 20:29:20" 
		geo = "49.168236527256,-122.857360839844,50km"
		for myfile in IDfiles:
			print "Openign IDFile: ", file
			myfp = open(myfile)
			mycount = 0
			for line in myfp:
				ID = line.strip()
				try:
					cursor.execute("INSERT INTO userIDs(UserID, DateAdded, Location) VALUES(%s, %s, %s)", (str(ID), realtime, geo))
				except MySQLdb.IntegrityError:
					#If the ID is duplicate, ignore it. 
					pass
				mycount = mycount + 1
				if mycount > 10:
					mycount = 0
					dbconn.commit()
	
	def grabIDs(self):
		#TODO: automatically grab IDs given a particular location
		#Right now only takes IDs from a file
		#put IDs grabbed into self.IDqueue
		#3 sample IDs:496655421, 14601890, 194357523
		
		samples = [496655421, 14601890, 194357523]
		time = datetime.datetime.now()
		geo = "49.168236527256,-122.857360839844,50km"
		for ID in samples:
			self.IDqueue.put((ID, time, geo))
	
	def putIDs(self):
		#TODO: take ID from self.IDqueueu
		#GeoCode: 49.168236527256,-122.857360839844,50km
		while True:
			ID, time, geo =  self.IDqueue.get(True)
			dbcursor = self.dbConn.cursor()
			try:
				dbcursor.execute("INSERT INTO userIDs(UserID, DateAdded, Location) VALUES(%s, %s, %s)", (str(ID), time, geo))
			except MySQLdb.IntegrityError:
				#If the ID is duplicate, ignore it. 
				pass
			self.dbConn.commit()
			
	def GrabIDFromDatabase(self, GrabberID):
		dbconn = self.connectToDB()
		cursor = dbconn.cursor()
		msg = "[DB ID Grabber " + str(GrabberID) + "] Spawned an ID Grabber to get from database"
		self.log(msg)
		cursor.execute("SELECT * FROM userIDs WHERE NotScanned=0 LIMIT 1")
		self.log2("[DB ID Grabber] Selected 1 rows from the Twitter Users database")
		row = cursor.fetchone()
		ID = row[0]		
		try:
			self.TweetIDQueue.put(ID, True, 30)
		except Queue.Full:
			self.log("[DB ID Grabber " + str(GrabberID) + "] ID Queue is Full, waiting for 5 seconds")
			dbconn.close()
			gevent.sleep(5)
			return
		cursor.execute("Update userIDs SET NotScanned=1 Where UserID=%s ;", str(ID))
		self.log2("[DB ID Grabber " + str(GrabberID) + "] ID grabber (GrabIDFromDatabase) got the userID: " + str(ID) + " Updated that into database now")
		dbconn.commit()
		dbconn.close()
		#TODO: Set The scanned time to now. 
	
	def resetUserDatabase(self):
		dbconn = self.connectToDB()
		cursor = dbconn.cursor()
		self.log("Clearing all rows that have been grabbed form the user database")
		while True:
			cursor.execute("SELECT * FROM userIDs WHERE NotScanned=1 LIMIT 1000")
			rows = cursor.fetchall()
			if len(rows) < 1:
				return
			for row in rows:
				ID = row[0]
				self.TweetGrabQueue.put(ID, True)
				cursor.execute("Update userIDs SET NotScanned=0 Where UserID=%s ;", str(ID))
				print ID
			dbconn.commit()
			
	def TweetInserter(self, InserterID):
		timeout = gevent.Timeout(800)
		timeout.start()
		try:
			myName = "[Tweet Inserter " + str(InserterID) +  "] "
			msg = myName + "is spawned \t\t"
			print colored(("\t" + msg),"white","on_grey")
			self.log(msg)
			dbConnection = self.connectToDB()
			cursor = dbConnection.cursor()
			self.log2(myName + "Made connection to database, with " + str(dbConnection))
			insertions = 0
			while insertions < 300:
				try:
					status = self.TweetGrabbedQueue.get(True, 10)
					text, UID, TweetID, HashTags, Time = status
					try:
						cursor.execute("INSERT INTO testTweets(UserID, TweetID, Text, Time, HashTags) VALUES(%s, %s, %s, %s, %s)", (str(UID), str(TweetID), text, Time, str(HashTags)))
					except MySQLdb.IntegrityError:
						self.log2("[Tweet Inserter] Encountered MYSQL Integrity error, Tweet already in database, skipping for now")
				except Queue.Empty:
					message = myName + "Queue empty timeout (probably due to deadlock), temporarily giving up control"
					gevent.sleep()
					self.log(message)			
				
					#If the ID is duplicate, ignore it. 
				dbConnection.commit()
				insertions = insertions + 1
			finishMsg = "Tweet Inserter " + str(InserterID) + " has made " +str(insertions) + " insertions, shutting down now. "
			self.log(finishMsg)
			print colored(finishMsg, "green")			
		except gevent.Timeout, t:
			if t is not gevent.Timeout:
				msg = myName + "Errored not with a timeout, this is the error message: " + str(t)
				self.log(msg)
			else:
				msg = myName + "Module timed out after 800 seconds. Cleaning up now. "
				self.log(msg)
				print colored(msg, "yellow")
		finally:
			timeout.cancel()
			dbConnection.commit()
			dbConnection.close()
			msg = "[Tweet Inserter "+ str(InserterID) +"] There are " + str(self.TweetGrabbedQueue.qsize()) + " still left in the Tweet Grabbed Queue"
			self.log(msg)
		return 
	
	def GrabTweetsByID(self, UID, Grabbernum):
		timeout = gevent.Timeout(1200)
		timeout.start()
		try:
			myName = "[Tweet Grabber " + str(Grabbernum) +  "] "
			msg = myName + "is spawned \t\t"
			print colored(('\t' + msg), "white", "on_grey")
			self.log(msg)
			api = self.TwiApi
			cutoff = datetime.datetime(2012, 11, 01)
			lastTweetID = 1401925121566576641
			Time = datetime.datetime.now()
			realtime = datetime.datetime.strptime(Time, "%Y-%m-%d %H:%M:%S")
			numTweets = 0
			while (realtime > cutoff and numTweets < 3200):
				try:
					statuses = api.get_user_timeline(user_id=UID, count=200, max_id=lastTweetID)
					self.log2("[Tweet Grabber "+ str(Grabbernum) +"] Just got a stack of statuses of size: " + str(len(statuses)))
					if len(statuses) is 0:
						stderrMessage = "[Tweet Grabber "+ str(Grabbernum) +"] Empty status queue is returned by Twitter, Assuming there's no more status in the user's history"
						self.log(stderrMessage)
						break
					for status in statuses:
						text = status[u'text'].encode('UTF-8')
						TweetID = status[u'id']
						HashTags = status[u'entities'][u'hashtags']
						Time = time.strftime('%Y-%m-%d %H:%M:%S', time.strptime(status[u'created_at'],'%a %b %d %H:%M:%S +0000 %Y'))
						try:
							self.TweetGrabbedQueue.put((text, UID, TweetID, HashTags, Time), True, 10)
						except Queue.Full:
							msg = "[Tweet Grabber "+ str(Grabbernum) +"] just hit 10 second queue full timeout (probably due to deadlock), yielding cycles for now"
							self.log2(msg) 
							gevent.sleep()
				except (twython.TwythonRateLimitError, twython.TwythonError) as e:
					if twython.TwythonRateLimitError in e:
						stderrMessage = "[Tweet Grabber "+ str(Grabbernum) +"] Hitting the limit (Twython returned twitter error), this ID Grabber is gonna back off for 300 seconds\n"
						self.log(stderrMessage)
						sys.stderr.write(colored(stderrMessage, "blue"))
						gevent.sleep(300)
						continue
					if twython.TwythonError in e:
						stderrMessage = myName + "just hit the SSL error. Backing off for 3 seconds to see if it comes back"
						self.log(stderrMessage)
						print colored(stderrMessage, "yellow", "on_gray")
						gevent.sleep(3)
				gevent.sleep()
				realtime = datetime.datetime.strptime(Time, "%Y-%m-%d %H:%M:%S")
				lastTweetID = TweetID -1
				numTweets = numTweets + len(statuses)
				msg =  "[Tweet Grabber "+ str(Grabbernum) +"] "+ str(numTweets) + " numTweets so far, for USERID: " + str(UID)
				self.log2(msg)			
		except gevent.Timeout, t:
			if t is not gevent.Timeout:
				msg = myName + "Errored not with a timeout, this is the error message: " + str(t)
				self.log(msg)
			else:
				msg = myName + "Module timed out after 1200 seconds. Cleaning up now. "
				self.log(msg)
				print colored(msg, "yellow")
		finally:
			timeout.cancel()
			msg = "[Tweet Grabber "+ str(Grabbernum) +"] Done grabbing tweets from this User: " + str(UID) + " and grabbed a total of: " + str(numTweets) + " Tweets."
			self.log(msg)
			print colored(msg, "green")
			msg = "[Tweet Grabber "+ str(Grabbernum) +"] There are " + str(self.TweetGrabbedQueue.qsize()) + " still left in the Tweet Grabbed Queue"
			self.log(msg)
		return 
	
	#Block until there's an ID to process on TweetGrabQueue
	def TweetGrabWorker(self, myNum):
		ID = self.TweetIDQueue.get()
		self.GrabTweetsByID(ID, myNum)
			
	def spawnTweetGrabbers(self):
		Producer = 1
		while True:
			self.TweetGrabPool.spawn(self.TweetGrabWorker, Producer)
			Producer = Producer +1
			gevent.sleep(1)
			
	def spawnTweetInserters(self):
		Consumer = 1
		while True:
			self.TweetInsertPool.spawn(self.TweetInserter, Consumer)
			Consumer = Consumer + 1
			gevent.sleep(1)			
		
	def spawnIDDBGrabbers(self):
		msg = "Spawning Grabbers to get IDs from database now"
		print colored(msg, "green")
		self.log(msg)
		IDGrabberNum = 1
		while True:
			if self.TweetIDQueue.full():
				gevent.sleep(10)
			else:
				self.IDGrabberPool.spawn(self.GrabIDFromDatabase, IDGrabberNum)
				IDGrabberNum = IDGrabberNum + 1
	
	def MonitorThread(self):
		#Monitors the varies pools and Queues make them print their own statuses into the log files.
		#If something is running for more than 20 minutes, kill it. 
		
		while True:
			gevent.sleep(10)
			msg = "[Montior] The pool thinks there are " + str(self.IDGrabberPool.free_count()) + " ID grabber slots, working on a current queue size of: " + str(self.TweetIDQueue.qsize()) + " out of :" + str(self.TweetIDQueue.maxsize)
			self.log(msg)
			for greenlet in self.IDGrabberPool:
				msg = "[Monitor] Currently alive ID Grabber: " + str(greenlet)
				if "kwargs" in dir(greenlet):
					msg = "[Monitor] Currently alive ID Grabber: " + str(greenlet.kwargs)
				elif "args" in dir(greenlet):
					msg = "[Monitor] Currently alive ID Grabber: " + str(greenlet.args)
				self.log2(msg)
			
			msg = "[Montior] The pool thinks there are " + str(self.TweetGrabPool.free_count()) + " available Tweet Grabber slots, and " + str(self.TweetInsertPool.free_count()) + " available Tweet Inserters slots on a current queue size of: " + str(self.TweetGrabbedQueue.qsize())
			self.log(msg)
			for greenlet in self.TweetGrabPool:
				if "args" in dir(greenlet):
					msg = "[Monitor] Currently alive Tweet Grabber: " + str(greenlet.args)
				else:
					msg = "[Monitor] Currently alive Tweet Grabber: " + str(greenlet)
				self.log2(msg)
			for greenlet in self.TweetInsertPool:
				if "args" in dir(greenlet):
					msg = "[Monitor] Currently alive Tweet Inserter: " + str(greenlet.args)
				else:
					msg = "[Monitor] Currently alive Tweet Inserter: " + str(greenlet)
				self.log2(msg)
				
	def printCurrentTime(self):
		msg = "Harvester client STarting time: " + str(datetime.datetime.now())
		print msg
		
	def __init__(self, ip):
		self.peerlist = []
		self.logger = HarvesterLog.HarvesterLog("client")
		self.logger2 = HarvesterLog.HarvesterLog("client_debug")
		self.numAPICalls = 0
		self.printCurrentTime()
		
		'''
		### Server module
		print "In client mode, attempting to connect to ", ip
		self.validateIP(ip)
		self.server_ip = ip
		self.server_port = 20002
		self.chatComm = self.connectToServer(self.server_ip)
		self.connectToOtherClients(self.chatComm)
		### // Server Module
		'''
		
		### Database Module
		print "Client attempting to connect to database"
		self.dbConn = self.connectToDB()
		self.testDBConn(self.dbConn)
		### // Database Module		
		
		'''
		### ID Grabbing Module 
		print "Starting ID grabbing module"
		self.IDqueue = Queue.Queue()
		self.IDGrabber = Greenlet.spawn(self.grabIDs)
		self.IDputter = Greenlet.spawn(self.putIDs)
		### // ID grabbing module
		'''
				
		### Input ID from Folder Module
		#self.IDFolderGrabber = Greenlet.spawn(self.FolderGrabber)
		### // Input ID Module
		
		'''
		### Chat Module
		print "Initializing chat module"
		self.clientListener = Greenlet.spawn(self.listenOnSocket)
		### // Chat Module
		'''
		
		### Tweet Grabber Module
		self.TwiAuth = twiAuth.twiAuth()
		self.TwiApi = self.TwiAuth.Api
		self.TweetIDQueue = Queue.Queue(6)
		self.IDGrabberPool = gevent.pool.Pool(3)
		Greenlet.spawn(self.spawnIDDBGrabbers)	
		
		self.TweetGrabbedQueue = Queue.Queue(600)
		self.TweetInsertPool = gevent.pool.Pool(4)
		self.TweetGrabPool = gevent.pool.Pool(3)
		Greenlet.spawn(self.spawnTweetInserters)
		Greenlet.spawn(self.spawnTweetGrabbers)		
		#self.resetUserDatabase()
		
		Greenlet.spawn(self.MonitorThread)

		while True:
			gevent.sleep(10)
		
		#TODO: Gracefully shutdown the program by shutdown
		
		### // Twwet Grabber Module
		
		
		
