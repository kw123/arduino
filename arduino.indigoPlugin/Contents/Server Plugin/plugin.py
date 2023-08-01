#! /usr/bin/env python
# -*- coding: utf-8 -*-
####################
# ARDUINO Plugin
# Developed by Karl Wachs
# karlwachs@me.com

import os, sys, pwd, socket
import requests

import time, copy
import json
import traceback


## these are constants:
## commands send to arduino, short form to save bytes
mapToArduino		= {"read":"rd","onoff":"wr","analogwrite":"aw","momentup":"mU","momentdown":"mD","pulseup":"pU","pulsedown":"pD","rampdown":"rD","rampup":"rU","rampupdown":"rC","config":"cf","prog":"pg","status":"st","count":"Co","countreset":"Cr"}
# and on the way back expand again
mapFromArduino		= {"rd":"read","wr":"ONoff","aw":"analogWrite","mU":"momentUp","mD":"momentDown","pU":"pulseUp","pD":"pulseDown","rD":"rampDown","rU":"rampUp","rC":"rampUPDown","cf":"config","pg":"prog","st":"status","Co":"Count","Cr":"CountReset"}

analogMax			= {"ESP1":1023,"ESP16":1023,"UNO":255,"MEGA":255,"FREE":100000,"mkr1000":1023}
doNotUsePin         = {"MEGA":["D7","D10","D11","D12","D13","D50","D51","D52","D53"],"UNO":["D7","D10","D11","D12","D13"],"mkr1000":[""],"ESP1":[""],"ESP16":[""],"FREE":[""]}
devTypes            = {"UNO":"arduino","MEGA":"arduino","mkr1000":"arduino","FREEE-Undefined":"arduino","ESP16":"arduino","ESP1":"arduino","sainsmart8-1":"sainsmart"}

Version				= "7.9.9"

pluginName           = "arduino"
thisPluginId         = "com.karlwachs."+pluginName

################################################################################
class Plugin(indigo.PluginBase):

####-----------------             ---------
	def __init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs):
		indigo.PluginBase.__init__(self, pluginId, pluginDisplayName, pluginVersion, pluginPrefs)
		
		self.pluginVersion		= pluginVersion
		self.pathToPlugin       = os.getcwd()+"/"
		## = /Library/Application Support/Perceptive Automation/Indigo 6/Plugins/piBeacon.indigoPlugin/Contents/Server Plugin
		p=max(0,self.pathToPlugin.find("/plugins/"))+1
		self.indigoPath         = self.pathToPlugin[:p]
		#self.errorLog(self.indigoPath)
		#self.errorLog(self.pathToPlugin)
	 
####-----------------             ---------
	def __del__(self):
		indigo.PluginBase.__del__(self)


###########################     INIT    ## START ########################
	
####----------------- @ startup set global parameters, create directories etc ---------
	def startup(self):
		if self.pathToPlugin.find("/"+pluginName+".indigoPlugin/")==-1:
			self.errorLog("---------------------------------------------------------------------------------------------------------------" )
			self.errorLog("---------------------------------------------------------------------------------------------------------------" )
			self.errorLog("---------------------------------------------------------------------------------------------------------------" )
			self.errorLog("---------------------------------------------------------------------------------------------------------------" )
			self.errorLog("--------------------------------------------------------------------------------------------------------------" )
			self.errorLog("The pluginname is not correct, please reinstall or rename")
			self.errorLog("It should be   /Libray/....../Plugins/"+pluginName+".indigPlugin")
			p=max(0,self.pathToPlugin.find("/Contents/Server"))
			self.errorLog("It is: "+self.pathToPlugin[:p])
			self.errorLog("please check your download folder, delete old *.indigoPlugin files or this will happen again during next update")
			self.errorLog("---------------------------------------------------------------------------------------------------------------" )
			self.errorLog("---------------------------------------------------------------------------------------------------------------" )
			self.errorLog("---------------------------------------------------------------------------------------------------------------" )
			self.errorLog("---------------------------------------------------------------------------------------------------------------" )
			self.sleep(1000)
			exit(1)
			return
		self.updateStatesList   = {}
		self.lastUpdate			= {}
		self.errorCount			= {}
		self.UpdateFrequency	= {}
		self.nextCheck			= {}
		self.debugLevel			= int(self.pluginPrefs.get("debugLevel", 0))
		self.urltimeout			= {}
		self.maxNofpinsPerMessage = {}
		try:
			self.setPinsDictLast= self.pluginPrefs["setPinsDictLast"]
		except:
			self.setPinsDictLast = indigo.Dict()
		try:
			self.programDictLast = self.pluginPrefs["programDictLast"]
		except:
			self.programDictLast = indigo.Dict()
		

		
		
		## throttle hhtp requests especially to WIFI shield
		self.minWaitbetweenhttp=.1
		self.lasthttp=0
		try:
			indigo.variables.folder.create("ArduinoLastMessage")
		except:
			pass


		self.myLog(255,"ARDUINO --V "+self.pluginVersion+"   initializing ")

		self.startDEVS=True

		self.pythonPath	= "/Library/Frameworks/Python.framework/Versions/Current/bin/python3"

		socket.setdefaulttimeout(5.0) # set timeout for url

		return

########################################


	########################################
	def deviceStartComm(self, dev):
		try:
			if self.startDEVS:
				dev.stateListOrDisplayStateIdChanged()  # update  from device.xml info if changed
			props = dev.pluginProps
			devType = dev.deviceTypeId
			devS = str(dev.id)

			self.myLog(1,"deviceStartComm  for " +dev.name)

			#make a copy
			self.lastUpdate[devS]					= 0
			self.errorCount[devS]					= 0
			self.UpdateFrequency[devS]				= props["UpdateFrequency"]
			self.urltimeout[devS]					= int(props["urltimeout"])
			try: self.maxNofpinsPerMessage[devS]    = int(props["maxNofpinsPerMessage"])
			except:  self.maxNofpinsPerMessage[devS]= 10
			self.nextCheck[devS]					= time.time()-100

			try:
				vari = indigo.variables[dev.name.replace(" ","")]
			except:
				try:
					self.myLog(255,"program PIN , could not update variable for "+dev.name.replace(" ","") )
				except:
					self.myLog(255,"program PIN , could not update variable ")



			self.myLog(1, " device :" + dev.name.replace(" ","") +" in deviceStartComm   refreshing  props :"+ str(props))

			pinToDelete = []
			for Pin in props:
				if Pin.find("Pin_")>-1:
					if Pin.find("Pin_F") > -1: pinToDelete.append(Pin);continue
					if Pin.find("Pin_N") > -1: pinToDelete.append(Pin);continue

					try:
						state= dev.states[Pin]
						if props[Pin] =="OFF" :
							#dev.updateStateOnServer(Pin,"OFF")
							self.addToStatesUpdateList(str(dev.id),Pin,"OFF")

						if props[Pin] == "O":
							if state == "0":
								#dev.updateStateOnServer(Pin,"ONoff:0")
								self.addToStatesUpdateList(str(dev.id),Pin,"ONoff:0")
							if state == "1":
								#dev.updateStateOnServer(Pin,"ONoff:1")
								self.addToStatesUpdateList(str(dev.id),Pin,"ONoff:1")
					except:
						pass 
						   
			for p in pinToDelete:
				del props[p]
		
			props["address"] = props["IPNumber"]
			dev.replacePluginPropsOnServer(props)


			dev.description="updtInt= "+props["UpdateFrequency"]+"[secs]"
			dev.replaceOnServer()
		except  Exception as e:
					if "{}".format(e).find("None") == -1: self.logger.error("", exc_info=True)
	
		return
	
	########################################
	def deviceStopComm(self, dev):
		self.myLog(1, " device :{} in deviceStopComm".format(dev.name)  )

		## the loop knows due to if not dev.enabled: continue
		return


####-----------------  confirm device configs after save---------
	def validateDeviceConfigUi(self,  valuesDict=None, typeId="", devId=0):

		dev = indigo.devices[devId]
		self.myLog(1, " device type:" + typeId)


		try:
			props = dev.pluginProps
			props["upDatePins"]=""
		except:
			props = ""
			props["upDatePins"] = ""
		for n in range(60):
			pin = "Pin_D"+str(n)
			if pin not in valuesDict: continue
			if pin not in props: continue
			if valuesDict[pin] == "OFF" and props[pin] != "OFF":
			  props["upDatePins"] += pin
		if  props["upDatePins"] != "":
			dev.replacePluginPropsOnServer(props)

		return True, valuesDict



####-----------------  set the geneeral config parameters---------
	def validatePrefsConfigUi(self, valuesDict):

		self.debugLevel	= int(valuesDict["debugLevel"])

		return True, valuesDict

####-----------------  set the geneeral config parameters---------
	def getMenuActionConfigUiValues(self, menuId):
		
		if menuId == "setPins":
			valuesDict = copy.copy(self.setPinsDictLast)
		elif menuId == "program":
			valuesDict = copy.copy(self.programDictLast)
		else:
			valuesDict = indigo.Dict()
		
		errorMsgDict = indigo.Dict()

		return (valuesDict, errorMsgDict)



####-----------------  set the geneeral config parameters---------

#	def getPrefsConfigUiValues(self):
#		valuesDict = indigo.Dict()   # must be initialize
#		return valuesDict


	########################################
	def dummyCALLBACK(self):
		return


	########### main loop -- start #########
	########################################
	def runConcurrentThread(self):

		count = 0
		self.sleep(0.5)
		self.myLog(1," looping to check devices for updates: ")
		lastReset = time.time()

		# program arduino at startup to read / write (I/O)
		for dev in indigo.devices.iter("self"):
			try:
				vari = indigo.variables[dev.name.replace(" ","")]
			except:
				indigo.variable.create(dev.name.replace(" ",""),"","ArduinoLastMessage")
			props = dev.pluginProps
			if  "suppressOfflineMessages" not in props:
				props["suppressOfflineMessages"]="0"
				dev.replacePluginPropsOnServer(props)
			
			if not dev.enabled: continue
			props = dev.pluginProps
			if "IPNumber" not in props: continue  # not yet setup completely
			if props["IPNumber"].find(".") ==-1: continue # not yet setup completely
			if "UpdateFrequency" not in props: continue  # not yet setup completely
			if   devTypes[dev.deviceTypeId] =="arduino":
				self.sendMsgToArduino(mapToArduino["status"]+'&',dev.id)# do a dummy read to set status
			elif devTypes[dev.deviceTypeId] =="sainsmart":
				self.sendMsgToSainsmart("Status" ,dev.id)# do a dummy read to set status


			devS = dev.id
			try: self.urltimeout[devS]              = int(props["urltimeout"])
			except:  self.urltimeout[devS]          = 10
			try: self.maxNofpinsPerMessage[devS]    = int(props["maxNofpinsPerMessage"])
			except:  self.maxNofpinsPerMessage[devS]= 10

			self.nextCheck[str(dev.id)] = time.time()+100  # this is for the case if we have no reads only output to pins  every 100 seconds
		self.startDEVS=False


		self.myLog(255, "init done")

		try:
			while True:
				now	=time.time()
				if now > lastReset +500:
					lastReset = now
					self.resetActionVariables()             

				for dev in indigo.devices.iter("self"):
					if not dev.enabled: continue
					
					deviceId= dev.id
					devS= str(deviceId)

					if devS not in self.nextCheck: continue  # not yet setup completely
					props = dev.pluginProps
					if "IPNumber" not in props: continue  # not yet setup completely
					if props["IPNumber"].find(".") ==-1: continue # not yet setup completely
					if "UpdateFrequency" not in props: continue  # not yet setup completely


					###  check status of this arduion, will only be active if no read function in the last 100 seconds------
					if self.nextCheck[devS] < time.time():
						self.myLog(1,"checking")
						if   devTypes[dev.deviceTypeId] =="arduino":
							out = self.sendMsgToArduino(mapToArduino["status"]+"&",dev.id)# do a dummy read to set status
						elif devTypes[dev.deviceTypeId] =="sainsmart":
							out =  self.sendMsgToSainsmart("Status" ,dev.id)# do a dummy read to set status

						if "upDatePins" in props and props["upDatePins"] !="":
							out["Status"] = "Online,resetPins"

						if out["Status"]!="Online, Configured":
							self.nextCheck[devS] +=10
							if (self.errorCount[devS] <10 or self.errorCount[devS]%100 ==1 ):
								if out["Status"]=="Online, Configured" :
									if  props["suppressOfflineMessages"] =="0":
										self.myLog(255,dev.name+"; current status is: "+out["Status"]+"  (test1)")
							if   devTypes[dev.deviceTypeId] =="arduino":
								self.setArduinoConfigIO(deviceId)
								out = self.setArduinoStatesValues(dev.id)
							elif devTypes[dev.deviceTypeId] =="sainsmart":
								out =  self.sendMsgToSainsmart("Status" ,dev.id)# do a dummy read to set status
							if out["Status"] == "Online, Configured" :
								if props["suppressOfflineMessages"] == "0":
									self.myLog(255,dev.name+" is "+out["Status"])
								self.nextCheck[devS] += 100
							else:
								self.lastUpdate[devS] = now
						else:
							self.nextCheck[devS] += 100

							
					now	=time.time()
					if self.lastUpdate[devS]+ float(self.UpdateFrequency[devS]) <= now:
						self.lastUpdate[devS] = now
						if dev.states["Status"]!="Online, Configured":
							self.errorCount[devS] += 1
							if (self.errorCount[devS] <10 or self.errorCount[devS]%100 == 1):
								if props["suppressOfflineMessages"] =="0":
									self.myLog(255,dev.name+"; current status is: "+ indigo.devices[deviceId].states["Status"]  +"  (test2)")
								
							self.nextCheck[devS] += 10
							self.lastUpdate[devS] = now+ min(5,0.5* float(self.UpdateFrequency[devS]))
							if   devTypes[dev.deviceTypeId] == "arduino":
								out = self.sendMsgToArduino(mapToArduino["status"]+':&',dev.id)# do a dummy read to set status
							elif devTypes[dev.deviceTypeId] == "sainsmart":
								out =  self.sendMsgToSainsmart("Status" ,dev.id)# do a dummy read to set status
							if out["Status"]!="Online, Configured":
									if   devTypes[dev.deviceTypeId] == "arduino":
										self.setArduinoConfigIO(deviceId)
										out = self.setArduinoStatesValues(dev.id)
									elif   devTypes[dev.deviceTypeId] == "sainsmart":
										out =  self.sendMsgToSainsmart("Status" ,dev.id)# do a dummy read to set status
									if out["Status"] == "Online, Configured":
										if  props["suppressOfflineMessages"] == "0":
											self.myLog(255,dev.name+" is back online and configured")
								
						### read all eligible pins ------
						if dev.states["Status"] == "Online, Configured" :
							pinValues = self.readAllPins(dev)
							if not "Status" in pinValues: continue
							if pinValues["Status"] == "Online, Configured":
									self.nextCheck[devS] += 100
									self.lastUpdate[devS] = now
									self.updatePinStates(dev,pinValues)
									
						 ### read all eligible pins end  ------
					self.executeUpdateStatesList()
				self.executeUpdateStatesList()
				self.sleep(0.5)
				count += 1
				
			
			
		except  Exception as e:
					if "{}".format(e).find("None") == -1: self.logger.error("", exc_info=True)
		
		self.myLog(255, " stopping plugin " )

		return


####-----------------  read pins---------
	def readAllPins(self, dev):
		props = dev.pluginProps
		out = ""
		pinValues = {"Status":"Offline"}
		try:
			if   devTypes[dev.deviceTypeId] =="arduino":
				for Pin in props:
					if "Pin_" not in Pin: continue			## props has all kinds of things pick Pin_D1 etc
					pin = Pin.strip("Pin_")
					if pin in doNotUsePin[dev.deviceTypeId]: continue
					if props[Pin] == "I" or  props[Pin] == "U" or props[Pin].upper() == "Y" or props[Pin].upper() == "Z":	## must be and I =Input pin, ignore rest
						out += mapToArduino["read"]+":"+pin+"&"
				if out !="":
						pinValues = self.sendMsgToArduino(out+'&',dev.id)

			elif devTypes[dev.deviceTypeId] =="sainsmart":
				pass
		except  Exception as e:
				if len(str(e))> 5:
					if "{}".format(e).find("None") == -1: self.logger.error("", exc_info=True)
					self.myLog(255, "dev " + dev.name )
					self.myLog(255, "out " + str(out) )
		
		return pinValues


		

####-----------------  update device/pin states---------
	def updatePinStates(self, dev,pinValues):
		devType = dev.deviceTypeId
		props = dev.pluginProps
		if   devTypes[dev.deviceTypeId] =="arduino":
				for pin in pinValues:
					if "Status" in pin: continue
					try:
						if pin.find("-") ==-1:
							if pin in doNotUsePin[devType]: continue
							Pin = "Pin_"+pin
							if Pin not in dev.states: continue
							if dev.states[Pin] != pinValues[pin]["values"]:
								#dev.updateStateOnServer(Pin,pinValues[pin]["values"])
								self.addToStatesUpdateList(str(dev.id),Pin,pinValues[pin]["values"])
					except:
						pass
		elif devTypes[dev.deviceTypeId] =="sainsmart":
			pass

####----------------- simply set arduino to correct I/O config for each pin---------
	def setArduinoConfigIO(self,deviceId):
		# program arduino at startup to read / write (I/O)
		output = {"Status":"Offline"}
		dev = indigo.devices[deviceId]
		props = dev.pluginProps
		try:
			if   devTypes[dev.deviceTypeId] =="arduino":
				out = ""
				for Pin in props:
					if "Pin_" not in Pin: continue
					## self.myLog(255, "Pin:" +str(Pin))
					if Pin.find("A") >-1: continue
					pin=Pin.strip("Pin_")
					if Pin.find("D") >-1:
						if pin in doNotUsePin[dev.deviceTypeId]: continue
						if Pin not in dev.states: continue

						if props[Pin] =="I":
							out += mapToArduino["prog"] + ':' + pin + '=I&'
						elif props[Pin] =="O":
							out += mapToArduino["prog"] + ':' + pin + '=O&'
						elif props[Pin] =="OFF":
							out += mapToArduino["prog"] + ':' + pin + '=U&'
						elif props[Pin] == "z" :
							out += mapToArduino["prog"] + ':' + pin + '=z&'
						elif props[Pin] == "Z" :
							out += mapToArduino["prog"] + ':' + pin + '=Z&'
						elif props[Pin] == "y" :
							out += mapToArduino["prog"] + ':' + pin + '=y&'
						elif props[Pin] == "Y" :
							out += mapToArduino["prog"] + ':' + pin + '=Y&'

					if props[Pin] !="I"  and props[Pin] !="O" and props[Pin] !="U" and props[Pin].upper() !="Z" and props[Pin].upper() !="Y":
						#dev.updateStateOnServer(Pin,"OFF")
						self.addToStatesUpdateList(str(dev.id),Pin,"OFF")

				if out == "":
					out = mapToArduino["prog"]+':S0=I&'
				output = self.sendMsgToArduino(out,dev.id)
				if "upDatePins"  in props and   props["upDatePins"] !="":
					props["upDatePins"] = ""
					dev.replacePluginPropsOnServer(props)
				self.sleep(0.1) ##  wait for things to settle down

			elif devTypes[dev.deviceTypeId] =="sainsmart":
				pass

		except  Exception as e:
					if "{}".format(e).find("None") == -1: self.logger.error("", exc_info=True)
		return output




####-----------------  set arduino to correct I/O config for each pin---------
	def setArduinoStatesValues(self,deviceId, pinsToUpdate="ALL"):
		# program arduino at startup to read / write (I/O)
		output={"Status":"Offline"}
		try:
			dev = indigo.devices[deviceId]
			props = dev.pluginProps
			out = ""
			pinsToUpdate = pinsToUpdate.upper()
			for Pin in props:
				##self.myLog(255, " props "+ str(Pin))
				if "Pin_" not in Pin: continue
				pin = str(Pin).strip("Pin_")
				if pin in doNotUsePin[dev.deviceTypeId]: continue
				if Pin not in dev.states: continue
				if pinsToUpdate != "ALL" and pin not in pinsToUpdate: continue
				state= str(dev.states[Pin])
				if props[Pin] =="O":
					if state =="": continue  # state not set yet, nothing to set
					if state =="0" or state=="1":
						cmdValue=["ONoff".lower(),state]
					else:
						cmdValue= state.split(":")
					try:
						##self.myLog(255, " cmdValue " + str(cmdValue))

						if len(cmdValue)>1:
							## to not write onetime signals to pins as they are only one time events , but write final state
							if cmdValue[0] == "momentUp":
								cmdValue[0] = "ONoff"
								cmdValue[1] = "0"
							elif cmdValue[0] == "momentDown":
								cmdValue[0] = "ONoff"
								cmdValue[1] = "1"
							elif cmdValue[0].find("rampDown") > -1:
								cmdValue[0] = "analogWrite"
								cmdValue[1] = cmdValue[1].split(",")[1]
							elif cmdValue[0].find("rampUp") > -1:
								cmdValue[0] = "analogWrite"
								cmdValue[1] = cmdValue[1].split(",")[2]
							out+=mapToArduino[cmdValue[0].lower()]+':'+pin+'='+cmdValue[1]+'&'
					except Exception as e :
						self.myLog(255, " error updating Pin state cmdValue {} {} {} ".format(Pin, state, cmdValue))
						self.logger.error("", exc_info=True)

				if props[Pin].upper() == "Y" or props[Pin].upper() == "Z":
					   out += mapToArduino["CountReset".lower()]+":" + pin + '&'


			if out != "":
				self.sleep(0.1) ##  wait for things to settle down
				output = self.sendMsgToArduino(out+'&',dev.id)
		
		except  Exception as e:
					if "{}".format(e).find("None") == -1: self.logger.error("", exc_info=True)
		return output

	def filterDevsSainsmart(self, valuesDict=None, filter="", typeId="", devId=""):
			list = []
			for dev in indigo.devices.iter(thisPluginId):
				if dev.deviceTypeId in devTypes and devTypes[dev.deviceTypeId].find("sainsmart") > -1:
					list.append((dev.id, dev.name))
			return list

	def filterDevsArduino(self, valuesDict=None, filter="", typeId="", devId=""):
			list = []
			for dev in indigo.devices.iter(thisPluginId):
				if dev.deviceTypeId in devTypes and devTypes[dev.deviceTypeId].find("arduino") > -1:
					list.append((dev.id, dev.name))
			return list


####----------------- ACTIONs  ---------
	def resetActionVariables(self):

		for dev in indigo.devices.iter("self"):
			try:
				indigo.variable.updateValue(dev.name.replace(" ",""),"")
			except:
				pass


####----------------- ACTIONs  ---------
	def reloadArduinoDeviceMenu(self, valuesDict, typeID):
		deviceId = int(valuesDict["device"])
		self.setArduinoConfigIO(deviceId)
		self.setArduinoStatesValues(deviceId)
		return  valuesDict



####----------------- ACTIONs  ---------
	def programCALLBACKmenu(self, valuesDict, typeID):
		self.programDictLast = copy.copy(valuesDict)
		self.pluginPrefs["programDictLast"]=copy.copy(valuesDict)
		self.setProgram(valuesDict, updateIndigo=True)
		return  valuesDict

####----------------- ACTIONs  ---------
	def programCALLBACKaction(self, action1):

		output = self.setProgram(action1.props,updateIndigo=True)
		self.myLog(2,str(output))
		try:
				dev = indigo.devices[int(action1.props["device"])]
		except:
				try:
					dev = indigo.devices[action1.props["device"]]
				except:
					self.myLog(255, " bad device  ID / name " + str(action1.props))
					return
		try:
			indigo.variable.updateValue(dev.name.replace(" ",""),str(output))
		except:
			try:
				indigo.variable.create(dev.name.replace(" ",""),"","ArduinoLastMessage")
				indigo.variable.updateValue(dev.name.replace(" ",""),str(output))
			except:
				self.myLog(255,"program PIN , could not update variable for "+dev.name.replace(" ","")+" "+str(action1.props) )

####----------------- ACTIONs  ---------
	def sendPinsCALLBACKaction(self, action1):
		self.sendPinsCALLBACKmenu(action1.props, typeId="")

####----------------- menue  ---------
	def sendPinsCALLBACKmenu(self,valuesDict,typeId=""):
		try:
			dev = indigo.devices[int(valuesDict["device"])]
			device =  int(valuesDict["device"])
		except:
				try:
					dev = indigo.devices[valuesDict["device"]]
					device =dev.id
				except:
					self.myLog(255, " bad device  ID / name " + str(valuesDict))
					return
		try:
			pins = valuesDict["pinsToBeSend"].upper().split(",")
			if len(pins) == 1:
				if not( "S" in pins[0] or "D" in pin[0] or "A" in pins[0] ):
					self.myLog(255, " bad pins " + str(valuesDict))
					return
		except:
			self.myLog(255, " bad device  ID / name " + str(valuesDict))
			return

		self.setArduinoStatesValues(device,pinsToUpdate=valuesDict["pinsToBeSend"])
		return  valuesDict


####----------------- menue  ---------
	def setPinCALLBACKmenu(self,valuesDict,typeId):
		self.setPinsDictLast = copy.copy(valuesDict)
		self.pluginPrefs["setPinsDictLast"]=copy.copy(valuesDict)
		self.setPin(valuesDict,updateIndigo=True)
		return  valuesDict

####----------------- ACTIONs  ---------
	def setPinCALLBACKaction(self, action1):

	
	
		try:
				dev = indigo.devices[int(action1.props["device"])]
		except:
				try:
					dev = indigo.devices[action1.props["device"]]
				except:
					self.myLog(255, " bad device  ID / name " + str(action1.props))
					return
		
		output = self.setPin(action1.props,updateIndigo=True)
		try:
			indigo.variable.updateValue(dev.name.replace(" ",""),str(output))
		except:
			try:
				indigo.variable.create(dev.name.replace(" ",""),"","ArduinoLastMessage")
				indigo.variable.updateValue(dev.name.replace(" ",""),str(output))
			except:
				self.myLog(255,"program PIN , could not update variable for "+dev.name.replace(" ","")+" "+str(action1.props) )

	   
		return



####----------------- ACTIONs  ---------
	def setPin(self, aprops1,updateIndigo=True):
		try:
			output = {}
			key = aprops1.keys()
			aprops = {}
			for p in key:
				ps = str(p).lower()
				aprops[ps] = aprops1[p]

			try:
				deviceId = int(aprops["device"])
				dev=indigo.devices[deviceId]
			except:
				try:
					dev=indigo.devices[aprops["device"]]
					deviceId = dev.id
				except:
					self.myLog(255, " bad device  ID / name " + str(aprops1))
					return {}

			self.myLog(2, "setPin  data: " +dev.name+ "  deviceTypeId:"+ dev.deviceTypeId+"  "+ str(devTypes))

			
			if devTypes[dev.deviceTypeId] =="arduino":
				output = self.setPinArduino( deviceId, dev, aprops ,updateIndigo=True)
			
			elif devTypes[dev.deviceTypeId] =="sainsmart":
				output = self.setPinSainsmart(deviceId, dev, aprops ,updateIndigo=True)

			else:
				self.myLog(255, "setPin bad devType" +dev.deviceTypeId+ "  "+ str(devTypes))
			
			
		except  Exception as e:
					if "{}".format(e).find("None") == -1: self.logger.error("", exc_info=True)
		self.executeUpdateStatesList()
		return output


			
	def setPinArduino(self, deviceId, dev, aprops, updateIndigo=True):
		try:
			CMD = ""; ONoff = "";aValue = "";msecUP = "";msecDOWN = ""
			
			pin = "D2"
			if "pin".lower() in  aprops:
				pin = aprops["pin"].upper()

			Pin = "Pin_"+pin

			if "CMD".lower() in aprops:
				CMD = aprops["CMD".lower()]
			if CMD =="":
				self.myLog(2," error in action command, CMD missing: "+str(aprops) )
				return output

			if "lowHIGH".lower() in aprops:
				lowHIGH = aprops["lowHIGH".lower()]

			if "aValue".lower() in aprops:
				aValue = aprops["aValue".lower()]
				if pin.lower().find("s") ==-1:  # check if integer for D and I, but not for S variables
					if pin[0].lower()=="d":
						try:
							aValue= str(max(0,min(int(aValue),analogMax[dev.deviceTypeId])))
						except:
							aValue="0"
			
			if "msecUP".lower()	 in aprops:
				msecUP	= aprops["msecUP".lower()]
				try:
					int(msecUP)
				except:
					msecUP="1000"
			if "msecDOWN".lower() in aprops:
				msecDOWN = aprops["msecDOWN".lower()]
				try:
					int(msecDOWN)
				except:
					msecDOWN = "1000"

			if "minValue".lower() in aprops:
				minValue = aprops["minValue".lower()]
				try:
					int(minValue)
				except:
					minValue = "0"
			else:
					minValue = "0"

			if "maxValue".lower()	in aprops:
				maxValue = aprops["maxValue".lower()]
				try:
					int(maxValue)
					if int(maxValue) > analogMax[dev.deviceTypeId]:
						maxValue = str(analogMax[dev.deviceTypeId])
				except:
					maxValue = str(analogMax[dev.deviceTypeId])
			else:
					maxValue = str(analogMax[dev.deviceTypeId])
			

			updateDev=False

			cmd = mapToArduino[CMD.lower()]+":"
			cms = CMD+":"
			cmd0 = ""

		##self.myLog(2, "arduino [device] \n"+ str(self.ARDUINO[device]))
			if  cmd !="config" and cmd != "rd:" and cmd.lower() !="cr:":  # if not set to write, first send command   prog to OUTPUT
				if Pin in aprops:
					if aprops[Pin] != "O":  # if not set to write, first send command   prog to OUTPUT
						updateDev=True
						cmd0= mapToArduino["prog"]+":"+pin+'=O&'
						props[Pin]="O"
			
			if CMD.lower() =="config".lower():
				cmd = cmd
				cms = cms
			if CMD.lower() =="status".lower():
				cmd = cmd
				cms = cms

			elif CMD.lower() == "read" :
				cmd += pin
				cms += pin

			elif CMD.lower() =="ONoff".lower():
				if lowHIGH=="":
					self.myLog(1," error in action command, lowHIGH missing: "+str(aprops) )
					return output
				cmd += pin+	'='+lowHIGH
				cms += lowHIGH

			elif CMD.lower() =="analogWrite".lower():
				if aValue=="":
					self.myLog(1," error in action command, aValue missing: "+str(aprops))
					return output
				cmd += pin+	'='+str(aValue)
				cms += aValue

			elif CMD.lower() =="momentUp".lower():
				if msecUP=="" :
					self.myLog(1," error in action command, msecUP missing: "+str(aprops) )
					return output
				cmd += pin+	'='+msecUP
				cms += msecUP

			elif CMD.lower() =="momentDown".lower():
				if msecDOWN =="":
					self.myLog(1," error in action command, msecDOWN missing: "+str(aprops) )
					return output
				cmd += pin+	'='+msecDOWN
				cms += msecDOWN

			elif CMD.lower() =="pulseUp".lower():
				if msecUP=="" or msecDOWN =="":
					self.myLog(1," error in action command, msecUP/DOWN missing: "+str(aprops) )
					return output
				cmd += pin+	'='+msecUP+','+msecDOWN
				cms += msecUP+','+msecDOWN

			elif CMD.lower() =="pulseDown".lower():
				if msecUP=="" or msecDOWN =="":
					self.myLog(1," error in action command, msecUP/DOWN missing: "+str(aprops) )
					return output
				cmd += pin+	'='+msecUP+','+msecDOWN
				cms += msecUP+','+msecDOWN
	
			elif CMD.lower() =="rampUp".lower():
				if msecUP=="":
					self.myLog(1," error in action command, msecUP missing: "+str(aprops) )
					return output
				cmd += pin+	'='+msecUP+","+minValue+","+maxValue
				cms += msecUP+","+minValue+","+maxValue

			elif CMD.lower() =="rampDown".lower():
				if msecDOWN=="":
					self.myLog(1," error in action command, msecDown missing: "+str(aprops) )
					return output
				cmd += pin+	'='+msecDOWN+","+minValue+","+maxValue
				cms += msecDOWN+","+minValue+","+maxValue

			elif CMD.lower() =="rampUPDown".lower():
				if msecDOWN=="":
					self.myLog(1," error in action command, msecDown missing: "+str(aprops) )
					return output
				if msecUP=="":
					self.myLog(1," error in action command, msecUp missing: "+str(aprops) )
					return output
				cmd+=pin+	'='+msecUP+','+msecDOWN+","+minValue+","+maxValue
				cms+=msecUP+','+msecDOWN+","+minValue+","+maxValue

			elif CMD.lower() == "CountReset".lower() :
				cmd += pin
				cms += cmd


			else:
				self.myLog(1," error in action command, CMD "+CMD+" mispelled: "+str(aprops) )
				return output


			
			self.myLog(1,"action= " +cmd0+cmd+'&')



			if "sendORset".lower() in aprops:
				self.myLog(1, "hello 1 ")
				if aprops["sendorset"].lower() == "setonly":
					output= {pin:{"values":cmd.split("=")[1]}}
				else:
					output = self.sendMsgToArduino(cmd0 + cmd + '&', deviceId)
			else:
				output = self.sendMsgToArduino(cmd0 + cmd + '&', deviceId)


			self.myLog(1, "returned= " + str(output))

			if updateIndigo and  CMD.lower() != "CountReset".lower():
				if pin in output:
					if output[pin]["values"].find("notConfigured")>-1:  ## error message could not update pin
						#dev.updateStateOnServer(Pin,output[pin]["values"])
						self.addToStatesUpdateList(str(dev.id),Pin,output[pin]["values"])
					else:
						#dev.updateStateOnServer(Pin,cms)
						self.addToStatesUpdateList(str(dev.id),Pin,cms)
				if updateDev:
					dev = indigo.devices[deviceId]
					props= dev.pluginProps
					props[Pin] = "O"
					dev.replacePluginPropsOnServer(props)


			return output
		except  Exception as e:
					if "{}".format(e).find("None") == -1: self.logger.error("", exc_info=True)


####----------------- ACTIONs  ---------
	def setProgram(self, aprops, updateIndigo=True):

		try:
			ret = ""
			self.myLog(1, "set prog: "+ str(aprops))
			key		= aprops.keys()
			for p in key:
				if "pin" == p.lower():
					pin = aprops[p].upper()
					break
			Pin		="Pin_"+pin
			for p in key:
				if "io" == p.lower():
					IO = aprops[p].upper()
					break

			try:
				deviceId	=int(aprops["device"])
				dev=indigo.devices[deviceId]
			except:
				try:
					dev=indigo.devices[aprops["device"]]
					deviceId	=dev.id
				except:
					self.myLog(255, " bad device  ID / name " + str(aprops1))
					return {}


			output={}
			self.myLog(1, "set to  "+ IO)
			if IO !="OFF":
				output = self.sendMsgToArduino(mapToArduino["prog"]+':'+pin+'='+IO+'&',deviceId)
			
			
			if updateIndigo:
				dev = indigo.devices[deviceId]
				props = dev.pluginProps
				props[Pin] = IO
				dev.replacePluginPropsOnServer(props)
				#dev.updateStateOnServer(Pin,IO)
				self.addToStatesUpdateList(str(dev.id),Pin,IO)


			return output
		except  Exception as e:
					if "{}".format(e).find("None") == -1: self.logger.error("", exc_info=True)
		

####----------------- send the message to the arduino @ ipnumber  ---------
	def sendMsgToArduino(self, out,deviceId):
		devS = str(deviceId)
		out = str(out)
		try:
			dev=indigo.devices[deviceId]
			try:
				lastOnline= dev.states["Status"]
			except:
				lastOnline= "Offline"
			socket.setdefaulttimeout(self.urltimeout[devS]) # set timeout for url
			output = {}
			output["Status"] = "Offline"
			Online = "OffLine"
			Onlinechanged = False
			IPNumber = str(dev.pluginProps["IPNumber"])
			props = dev.pluginProps
			out = out.strip("&")
			count = out.count('&') +1############# split into chuncks < xx,  for slow connections, small memeory on arduino ie used forf other things.
									 ############# ==> can reduce the input buffer buf1..  it is 7 bytes / pin and read for 16 pins = 112ytes, for 5 it would be 35bytes
			nPacks = int(count //self.maxNofpinsPerMessage[devS])
			items = out.split("&")
			for i in range(0,nPacks+1):
				out = ""
				j0 = self.maxNofpinsPerMessage[devS]*i
				j1 = self.maxNofpinsPerMessage[devS]*(i+1)
				for j in range( j0, min(j1,count)  ):
					out+= items[j] +'&'
				self.myLog(2, "i, out  {}  {}".format(i, items))
				if out == "": continue
				while self.lasthttp + self.minWaitbetweenhttp > time.time():
					self.sleep(0.1)
				self.lasthttp = time.time()
				try:
					start = time.time()
					url = 'http://'+IPNumber+'/?'+out+'?'
					self.myLog(2,url)
					try:
						ret= str(requests.get(url, timeout=8).content)
						output = self.parseFromArduino(ret,output)
						self.myLog(2,"http round trip : {}[sec]".format(time.time()-start))
						
						Online ="Online, Configured"
						if output["Status"]=="Online, Not Configured":
							Online="Online, Not Configured"
							self.errorCount[devS] += 1
							self.myLog(2,"not configured, break loop {}".format(output))
							break
						else:
							self.errorCount[devS] = 0
						self.lasthttp = time.time()
					except Exception as e:
						if self.errorCount[devS] < 5:
							if str(e).find("timed out" ) >-1:
								self.myLog(2,"connection to arduino >{}< timed out ".format(dev.name))
							else:
								self.myLog(255, "connection to arduino >{}".format(dev.name) )
								self.logger.error("", exc_info=True)
						self.errorCount[devS] +=1
						Online="Offline"
				except  Exception as e:
					if self.errorCount[devS] < 5:
						if "{}".format(e).find("None") == -1: self.logger.error("", exc_info=True)
					output["Status"]="Offline"
					Online="Offline"
					self.errorCount[devS] += 1

				if self.errorCount[devS] == 0:
					self.myLog(2,str(output))
				self.sleep(0.05)

			if lastOnline !=Online and deviceId != 0:
				#dev.updateStateOnServer("Status",Online)
				self.addToStatesUpdateList(str(deviceId),"Status",Online)
			return output
		except  Exception as e:
					if "{}".format(e).find("None") == -1: self.logger.error("", exc_info=True)



####----------------- parse and unparse arduino com ---------
	def parseFromArduino(self, inp, output):
#		try:
			##			inp=">>wr:D0=316&rd:A1=306&rd:D0=1&"
			##			out={"D0":{"cmd":write","values":"316"},"A1":{"cmd":read","values":"316"},"D0":{"cmd":read","values":"1"}}
			self.myLog(2,"msg from arduino: {}".format(inp))
			out = output
			out["Status"] = "Online,No Data"
			if len(inp)<3: return out 
			if inp.find(">>notConfigured") >-1:
				out["Status"] = "Online, Not Configured"
				return out
			if inp.find(">>Configured") >-1:
				out["Status"] = "Online, Configured"
				return out
			out["Status"] = "Online, Configured"
			
			o = inp.strip("&\r\n").strip(">").replace("&&","&")  ## fix for error in INO file, sends 2 && sometimes
			p = o.split("&") ## one element for each pin --> [write:D0=316,read:A1=306,read:D0=1,]
			pin = "-1"

			for p1 in p:  ## looks like: write:D0=316   or  read:A1=306  or read:D0=1  or ""

				if len(p1) < 2: continue # in case string is not complete or empty


				pK = p1.find(":") ## find FIRST occurence allow for  : in string
				self.myLog(2, "parse 1 "+ str(pK)+ " " + str(p1) )
				if pK > 0:
					p2 = [p1[0:pK],p1[pK+1:len(p1)]] # split command and rest  -->  [ rd, a1=306 ]
					self.myLog(2, "parse p2 "+ str(p2))
					try:
						cmd = mapFromArduino[p2[0]]  # -->  rd--> read, wr --> write ...
						self.myLog(2, "parse cmd "+ str(cmd))
						try:
							pE = p2[1].find("=")  ## find FIRST occurence allow for  = in string --> 2 in example
							self.myLog(2, "parse pE "+ str(pE))
							if pE > 0:
								p3 = [ p2[1][0:pE], p2[1][pE+1:len(p2[1])] ]  # split pin# and values  --> [ A1, 306 ]
								pin = p3[0] # --> A1
								self.myLog(2, "parse pE>0 "+ str(pin)+" "+  str(p3))
								try:
									values = p3[1] # --> 306
								except:
									pin = p2[1]  # just in case
									values = ""
							else:
								pin = p2[1]  #  == all of second part here it would be A1=306 
								values= ""
						except:
							cmd = "";pin = "-1"; values = "" # unknow error
					except:
						cmd = "";pin = "-1"; values = ""  # unknow error
							
					out[pin] = {"cmd":cmd, "values":values}
				else:
					out[pin]=  {"cmd":"", "values":""} # empty 
				
			return out
#		except:
#			self.myLog(2, "parse error "+ str(inp) )
#			return out

#>>rd:A0=207&rd:A1=261&rd:A2=243&rd:A3=262&rd:A4=268&rd:A5=238&rd:D0=notUseabl
##  {'Status': 'Online, Configured', 'F0': {'cmd': 'read', 'values': '2.09'}, 'F2': {'cmd': 'read', 'values': '0.00'}, 'F3': {'cmd': 'read', 'values': '0.00'}, 'F4': {'cmd': 'read', 'values': '9.90'}, 'F1': {'cmd': 'read', 'values': '0.00'}, 'N4': {'cmd': 'read', 'values': '5'}, 'S1': {'cmd': 'read', 'values': 'Humidity: 50%'}, 'S0': {'cmd': 'read', 'values': 'Temperature= 2'},
##  'A1': {'cmd': 'read', 'values': '256'}, 'A0': {'cmd': 'read', 'values': '207'}



####----------------- ACTIONs  ---------
	def setPinSainsmart(self, deviceId, dev, aprops ,updateIndigo=True):
		try:
			self.myLog(2,"setPinSainsmart: {} {}".format(dev.name, aprops))
			output ={"Status":""}
			CMD=""
			if "lowhigh" in aprops:
				CMD = aprops["lowhigh"]
			if CMD =="":
				self.myLog(255," error in action command, CMD missing: {}".format(aprops) )
				return output

			output= self.sendMsgToSainsmart( CMD,deviceId)

		except  Exception as e:
					if "{}".format(e).find("None") == -1: self.logger.error("", exc_info=True)
		return output


	def actionControlDimmerRelay(self, action, dev0):
		ONoff ="0"
		if action.deviceAction == indigo.kDeviceAction.TurnOn:
			ONoff="1"
		elif action.deviceAction == indigo.kDeviceAction.TurnOff:
			ONoff="0"
		self.sendMsgToSainsmart(ONoff,dev0.id)
		self.executeUpdateStatesList()


####----------------- send the message to the arduino @ ipnumber  ---------
	def sendMsgToSainsmart(self, OnOrOff,deviceId):
		devS= str(deviceId)
		try:
			dev=indigo.devices[deviceId]
			try:
				lastOnline= dev.states["Status"]
			except:
				lastOnline= "Offline"
			socket.setdefaulttimeout(self.urltimeout[devS]) # set timeout for url
			output={}
			output["Status"] = "Offline"
			Online           = "OffLine"
			Onlinechanged    = False
			props            = dev.pluginProps
			relay            = dev.pluginProps["relay"].split(",")
			self.myLog(2,"dev, relay:{}  OnOrOff:{}  relay:{}".format(dev.name, OnOrOff, relay))
			# relay is up,down,RELAY-xx,on,off,status-page
			relayName        = str(relay[2])
			page             = str(relay[5])

			if OnOrOff.lower() == "status": 
				if dev.states["onOffState"] =="ON":
					OnOrOff ="1"
				else:
					OnOrOff ="0"

			if dev.pluginProps["reverseOut"] =="1":
				if OnOrOff =="1":
					OnOrOff ="0"
				else:
					OnOrOff ="1"


			if   OnOrOff == "1":   
				cmd          = relay[3]
				ONoff        = relay[0]
			elif OnOrOff == "0": 
				cmd          = relay[4]
				ONoff        = relay[1]
			else:
				self.myLog(255,"dev, relay:{} OnOrOff wrong:{}".format(dev.name, OnOrOff))
				return output


				
			if True:
				self.lasthttp = time.time()
				try:
					start= time.time()
					url='http://'+str(dev.pluginProps["IPNumber"])+'/'+str(dev.pluginProps["portNumber"])+"/"+page
					#self.myLog(255,"Sainsmart page     "+ url)
					try:
						ret= str(requests.get(url, timeout=8).content)
						output = str(self.parseFromSainsmart(ret,relayName))
						#self.myLog(255,"http round trip : "+str(time.time()-start)+"[sec]\n  "+ str(ret) +"\n  "+ str(output))
						if output["relay"] == "":  # do it again, have to be on the right page
							url='http://'+str(dev.pluginProps["IPNumber"])+'/'+str(dev.pluginProps["portNumber"])+"/"+page
							self.myLog(2,"Sainsmart redo page   "+ url)
							ret= str(requests.get(url, timeout=8).content)
							output = self.parseFromSainsmart(ret,relayName)
							#self.myLog(255,"http round trip : "+str(time.time()-start)+"[sec]\n  "+ str(ret) +"\n  "+ str(output))
						
						Online = output["Status"]
						self.errorCount[devS]=0
						self.lasthttp = time.time()
						if output["relay"] != ONoff and  ONoff !="":
							start= time.time()
							url='http://'+str(dev.pluginProps["IPNumber"])+'/'+str(ev.pluginProps["portNumber"])+"/"+cmd
							self.myLog(2,url)
							try:
								ret= str(requests.get(url, timeout=8).content)
								output = self.parseFromSainsmart(ret,relayName)
								Online = output["Status"]
								#self.myLog(255,"http round trip set : "+str(time.time()-start)+"[sec]\n  "+ str(ret) +"\n  "+ str(output))
						
							except Exception as e:
								if self.errorCount[devS] < 5:
									if str(e).find("timed out" ) >-1:
										self.myLog(2,"connection to arduino >{}< timed out ".format(dev.name))
									else:
										self.myLog(255, "connection to arduino >{}".format(dev.name))
										self.logger.error("", exc_info=True)
								self.errorCount[devS] +=1
 


					except Exception as e:
						if self.errorCount[devS] < 5:
							if str(e).find("timed out" ) >-1:
								self.myLog(2,"connection to arduino >{}< timed out ".format(dev.name))
							else:
								self.myLog(255, "connection to arduino >{}".format(dev.name))
								self.logger.error("", exc_info=True)
						self.errorCount[devS] +=1
						Online="Offline"

				except  Exception as e:
					if self.errorCount[devS] < 5:
						if "{}".format(e).find("None") == -1: self.logger.error("", exc_info=True)
					output["Status"]="Offline"
					Online="Offline"
					self.errorCount[devS] +=1

				if self.errorCount[devS] ==0:
					self.myLog(2,str(output))
				self.sleep(0.05)

			if lastOnline !=Online and deviceId !=0:
				self.addToStatesUpdateList(str(deviceId),"Status",Online)

			if "relay"  in output:
				if dev.pluginProps["reverseOut"] =="1":
					if output["relay"] =="ON":
						output["relay"] ="OFF"
					else:
					   output["relay"]  ="ON"

				if output["relay"] != dev.states["onOffState"]:
					if output["relay"] =="ON":
						self.addToStatesUpdateList(str(deviceId),"onOffState",True)
					if output["relay"] =="OFF":
						self.addToStatesUpdateList(str(deviceId),"onOffState",False)
		except  Exception as e:
				#if len(e)>1:
					if "{}".format(e).find("None") == -1: self.logger.error("", exc_info=True)
		return output


####----------------- parse and unparse arduino com ---------
	def parseFromSainsmart(self,inp,relayName):
		##			inp="Relay-02: <font color="#FF0000"> OFF&nbsp&nbsp</font> 
		self.myLog(2,"msg from Sainsmart: "+ inp)
		out= {"Status":"Online, Not Configured", "relay":""}
		if len(inp)<10: return out

					
		try:
			if inp.find(relayName) >-1:
				relay           = inp.split(relayName)[1]
				relay           = relay.split("&nbsp&nbsp</font>")[0]
				relay           = relay.split('"> ')[1]
				if relay.find("ON") >-1:
					out["relay"]    = "ON"
				else:
					out["relay"]    = "OFF"
				
				out["Status"]   = "Online, Configured"
		except  Exception as e:
			if "{}".format(e).find("None") == -1: self.logger.error("", exc_info=True)
			out["Status"]    = "Online, Not Configured"
		return out





####----------------- logfile  ---------
	def myLog(self,msgLevel,text,type=""):
		if msgLevel == 0: return
		if msgLevel ==-1:
			indigo.server.log("--------------------------------------------------------------")
			indigo.server.log(text)
			indigo.server.log("--------------------------------------------------------------")
			return
		if msgLevel ==-2:
			self.errorLog("----------------------------------------------------------------------------------" )
			self.errorLog(text)
			self.errorLog("----------------------------------------------------------------------------------" )
			return
		if msgLevel == 255:
			if type =="": indigo.server.log(text)
			else:		  indigo.server.log(text,type=type)
			return
		if self.debugLevel == 255:
			if type =="": indigo.server.log(text)
			else:		  indigo.server.log(text,type=type)
			return
		if self.debugLevel&msgLevel >0:
			if type =="": indigo.server.log(text)
			else:		  indigo.server.log(text,type=type)
			return




	def addToStatesUpdateList(self,devId,key,value):
		try:

			if devId not in self.updateStatesList: 
				self.updateStatesList[devId]=[]
			for n in range(len(self.updateStatesList[devId])):
				entry = self.updateStatesList[devId][n]
				if ( value != entry["value"] ):
					self.updateStatesList[devId].append({"key":key,"value":value})
					return
			self.updateStatesList[devId].append({"key":key,"value":value})

		except:
			self.updateStatesList={}

	def executeUpdateStatesList(self,newStates=""):
		try:
			if len(self.updateStatesList) ==0: return
			for devId in self.updateStatesList:
				if len(self.updateStatesList[devId]) > 0:
					dev =indigo.devices[int(devId)]
					actualChanged = []
					for n in range(len(self.updateStatesList[devId])):
						value = self.updateStatesList[devId][n]["value"]
						key   = self.updateStatesList[devId][n]["key"]
						if  newStates == "":
							if value != dev.states[key]:
									actualChanged.append(self.updateStatesList[devId][n])
						else:            
							if value != newStates[key]:
								newStates[key] = value

					if  newStates == "":
						self.updateStatesList[devId]=[]            
						if actualChanged !=[]:
							#indigo.server.log("%14.3f"%time.time()+"  "+dev.name.ljust(25)  + str(actualChanged)) 
							dev.updateStatesOnServer(actualChanged)
			if  newStates != "":  
				return newStates              
		except  Exception as e:
					if "{}".format(e).find("None") == -1: self.logger.error("", exc_info=True)
