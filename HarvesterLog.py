##HarvesterLog.py
from __future__ import print_function
from easytime import easytime

class HarvesterLog:
	def now(self):
		mytime = easytime.utcnow().convert('Canada/Pacific')
		time = str(mytime).split(".")[0]
		return time
		
	def log(self, message):
		curTime = self.now()
		myMessage = curTime + " : " + message
		print(myMessage, file=self.file)
		
	def close(self):
		self.file.close()
		
	def __init__(self, HarvesterType):
		#Make a new log file.
		self.myType = HarvesterType
		logfolder = 'log/'
		startTime = self.now()
		name = logfolder + self.myType + startTime + '.log'
		self.file = open(name, 'w')
		
	