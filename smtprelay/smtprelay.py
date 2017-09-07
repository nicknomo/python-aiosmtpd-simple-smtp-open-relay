import asyncio
import threading
import time
import re
import sys
import os
import dns.resolver
from smtplib import SMTP as Client
from aiosmtpd.controller import Controller
from aiosmtpd.smtp import Envelope

HELOname = 'myhost.mydomain.com'
smtprelayport = '10025'
bindip = '127.0.0.1'


class mailsender(threading.Thread):	

	email_to = ''
	email_from = ''
	data = ''
	
		
	def __init__(self,mail_from,recipient,envelopedata):
		threading.Thread.__init__(self)
		self.email_from = mail_from
		self.email_to = recipient
		self.data = envelopedata.content
		self.envelope = envelopedata
		

	def generateNDR(self,recipient,e):
		try:
			iplist = self.getmxrecords(recipient)
			if not iplist: raise Exception('Could Not send email. There were no IPs returned from DNS lookup, domain is likely malformed')
			
			for ip in iplist:
				try:
					client = Client(ip, '25',HELOname,8)
					#unfortunately, sending the additional options did not work well in SMTPlib.
					#r = client.sendmail(self.email_from, [recipient], self.data, self.envelope.mail_options, self.envelope.rcpt_options)
					message = str(e)
					r = client.sendmail(recipient, [recipient], message)
					break
				
				except BaseException as e:
					print(e)				
		
		except BaseException as e:
			print(e)
		
		
	## Here we run the actual DNS query
	def rundnsquery(self,dnsrequest,host):	
		#this is a list of the DNS results in IP form
		dnslist = []	
		#This is a list of the MX hostnames we'll need to search for
		mxlist = []	
		
		#first we get answers to the MX record request
		try:
		    	answers = dnsrequest.query(host, 'MX')
		    	for rdata in answers:
		    		dnsmx = rdata.to_text()
		    		#MX records return a priority and a hostname
		    		#We need to separate the two for proper sorting
		    		temp = dnsmx.split()
		    		tempint = int(temp[0])
		    		mxlist.append((tempint,temp[1]))
		    	
		except BaseException as e:
			print(e)
		
		#Here we sort the mx records by priority, so the most important are chosen first
		mxlist = sorted(mxlist, key=lambda tup: tup[0])
		
		#if there are no mx records, we return an empty set
		if not mxlist: return []
		
		#For each MX record, we are going to resolve an ipv4 address and ipv6 address
		#We will do IPv4 first because as of right now, ipv6 adoption is limited.
		for mxrecord in mxlist:
			try:
			    	answers = dnsrequest.query(mxrecord[1], 'A')
			    	for rdata in answers:
			    		dnsip = rdata.to_text()
			    		dnslist.append(dnsip)
		    	
			except BaseException as e:
				print(e)

		#Now we'll gather ipv6 ips', and put them at the end of the list
		for mxrecord in mxlist:

			try:
				answers = dnsrequest.query(mxrecord[1], 'AAAA')
				for rdata in answers:
			    		dnsip = rdata.to_text()
			    		dnslist.append(dnsip)
	
			except BaseException as e:
				print(e)	
		
		#Hopefully we'll have IP addresses to return now					
		if (dnslist): 
			return dnslist
		else:
			return []

	#This will gather MX records and return IP addresses
	def getmxrecords(self,email):
		_, _, domain = email.partition('@')
		dnsrequest = dns.resolver.Resolver()
		dnsrequest.timeout = 4
		dnsrequest.lifetime = 8
		dnslist = []	
		
		try:
			#We do most of the work in the rundnsquery function
			dnslist = self.rundnsquery(dnsrequest,domain)
			if (dnslist): return dnslist
		
		except BaseException as e:
			print(e)
			#If we fail, we need to return an empty set
			return []
		
	
	def run(self):	
		self.sendemail(self.email_to)
	
	def sendemail(self,recipient):
		try:
			iplist = self.getmxrecords(recipient)
			
			if not iplist: raise Exception('Could Not send email to ' + self.email_to + '. There were no IPs returned from DNS lookup, the domain is likely malformed')
			for ip in iplist:
				try:
					client = Client(ip, '25',HELOname,8)
					#unfortunately, sending the additional options did not work well in SMTPlib.
					#r = client.sendmail(self.email_from, [recipient], self.data, self.envelope.mail_options, self.envelope.rcpt_options)
					r = client.sendmail(self.email_from, [recipient], self.data)
					break
			
				except BaseException as e:
					print(e)
					self.generateNDR(self.email_from,e)
			
		except BaseException as e:
			print(e)
			self.generateNDR(self.email_from,e)
	
	





class CustomHandler:

	def validate(self, email):
		if len(email) > 7:
			if re.match("(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$)", email) != None:
				return True
			return False

	async def handle_RCPT(self, server, session, envelope, address, rcpt_options):
		valid = False
		try:
			valid = self.validate(address)
		except BaseException as e:
	        	print(e)
	        	
		if not valid:
			return '501 5.5.4 invalid email address'
		envelope.rcpt_tos.append(address)
		return '250 OK'

	async def handle_DATA(self, server, session, envelope):
	        peer = session.peer
	        mail_from = envelope.mail_from
	        rcpt_tos = envelope.rcpt_tos
	        data = envelope.content         # type: bytes
	        threads = list()
	        # Process message data...
	        error_occurred=False
	        try:
	        	for recipient in rcpt_tos:
	        		send = mailsender(mail_from,recipient,envelope)
	        		send.start()
	        	
	        except BaseException as e:
	        	print(e)
	        	
	        if error_occurred:
	            return '500 Could not process your message'
	        return '250 OK'


if __name__ == '__main__':
	handler = CustomHandler()
	controller = Controller(handler, hostname=bindip, port=smtprelayport)
	# Run the event loop in a separate thread.
	controller.start()
	

	input('SMTP server running. Press Return to stop server and exit.')
	controller.stop()
