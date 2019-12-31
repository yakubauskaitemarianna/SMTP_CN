import socket
from sys import platform
from subprocess import check_output
import time
import telnetlib
import subprocess
import smtplib

#output = check_output("telnet localhost 25", shell=True).decode()

from smtplib import SMTP

#to_addr = input("input email to >> ")
#from_addr = input("input email from >> ")
#msg = ""
#while input_m = input() != "\n\n":
#    msg += input_m

from_addr = "mariannaraven@gmail.com"
to_addr = "mariannaraven@gmail.com"
msg = "HELLO"

with SMTP("localhost:25") as smtp:
    noop_answer = smtp.noop()
    if noop_answer == (250, b'Ok'):
        try:
            helo_answer = smtp.helo(name="nours.com")
            smtp.sendmail(from_addr, to_addr, msg)
        except SMTP.SMTPRecipientRefused:
            print("ERROR: Recipient refused")
        except SMTP.HeloError:
            print("ERROR: Helo error")
        except SMTP.SMTPSenderRefused:
            print("ERROR: Sender Refused")
        except SMTP.DataError:
            print("ERROR: Data eror")

    else:
        print("ERROR: NOOP answer not equal (250, OK)")
        exit()
