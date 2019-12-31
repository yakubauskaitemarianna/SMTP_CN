import socket
import os
import sys
import dns.resolver
import re
import _thread
import threading
import shutil

def HELO(args, s, client_address, state):
    fileName = str(client_address[1]) + '.txt'
    if len(args) != 2:
      s.send("501 Syntax: HELO hostname \n".encode())
      return

    if state['HELO'] == False:
      with open(fileName, 'w') as the_file:
        the_file.write(" ".join(args) + "\n")
      state['HELO'] = True
      state['file'] = client_address[1]
      state['domain'] = args[1]
      s.send(("250 "+ str(client_address[1]) + " OK \n").encode())

    else:
      open(fileName, 'w').close()
      with open(fileName, 'a') as the_file:
        the_file.write(" ".join(args) + "\n")
      state['HELO'] = False
      state['MAIL'] = False
      state['RCPT'] = False
      state['completedTransaction'] = False
      state['HELO'] = True
      s.send(("250 "+ str(client_address[1]) + " OK \n").encode())

def MAIL(args, s, client_address, state):
    fileName = str(state['file']) + '.txt'
    if state['HELO'] == False:
      s.send("503 5.5.1 Error: send HELO/EHLO first \n".encode())
    else:
      if state['MAIL'] == False:
        if len(args) != 2:
          s.send("501 5.5.4 Syntax: MAIL FROM:<address> \n".encode())
          return
        checkSyntax = re.match("(^FROM:<[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+>$)", args[1], re.IGNORECASE)
        if(checkSyntax):

          if state['data'] == False:
            with open(fileName, 'a') as the_file:
              the_file.write(" ".join(args) + "\n")
            state['MAIL'] = True
            s.send("250 2.1.0 Ok \n".encode())
          else:
              state['file'] = state['file'] + 1
              fileName = str(state['file']) + '.txt'
              with open(fileName, 'a') as the_file:
                the_file.write("helo " + state['domain'] + "\n")
                the_file.write(" ".join(args) + "\n")
              state['MAIL'] = True
              state['completedTransaction'] = False
              s.send("250 2.1.0 Ok \n".encode())
        else:
          s.send("501 5.1.7 Bad sender address syntax \n".encode())
      else:
        s.send("503 5.5.1 Error: nested MAIL command \n".encode())

def RCPT(args, s, client_address, state):
  if state['MAIL'] == True and state['HELO'] == True:
    if len(args) != 2:
      s.send("501 5.5.4 Syntax: RCPT TO:<address> \n".encode())
      return
    checkSyntax = re.match("(^TO:<[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+>$)", args[1], re.IGNORECASE)
    if(checkSyntax):
      state['recipient'] = checkSyntax.group()
      fileName = str(state['file']) + '.txt'
      with open(fileName, 'a') as the_file:
        the_file.write(" ".join(args) + "\n")
      state['RCPT'] = True
      s.send("250 2.1.5 Ok \n".encode())
    else:
      s.send("501 5.1.3 Bad recipient address syntax \n".encode())
  else:
    s.send("503 5.5.1 Error: need MAIL command \n".encode())

def DATA(args, s, client_address, state):
  fileName = str(state['file']) + '.txt'
  if state['MAIL'] == True and state['HELO'] == True and state['RCPT'] == True:
    s.send("354 End data with <CR><LF>.<CR><LF> \n".encode())
    data = recieveData(s, state)
    with open(fileName, 'a') as the_file:
      the_file.write("data \n")
      the_file.write(data)
      the_file.write("quit \n")
    state['MAIL'] = False
    state['RCPT'] = False
    s.send(("250 queued " + str(state['file']) + " \n").encode())
    state['data'] = True
    state['completedTransaction'] = True
    _thread.start_new_thread(relayData, (state['file'], state))
  elif state['MAIL'] == True and state['RCPT'] == False:
    s.send("554 5.5.1 Error: no valid recipients \n".encode())
  else:
    s.send("503 5.5.1 Error: need RCPT command \n".encode())

def NOOP(args, s, client_address, state):
  s.send("250 Ok \n".encode())

def QUIT(args, s, client_address, state):
  state['loop'] = False
  s.send("221 2.0.0 Bye \n".encode())
  s.close()
  if state['completedTransaction'] == False:
    fileName = str(state['file']) + '.txt'
    os.remove(fileName)

def VRFY(args, s, client_address, state):
  print(args)
  if len(args) > 2:
    s.send("501 5.5.4 Syntax: VRFY address \n".encode())
    return
  checkSyntax = re.match("TO:<\w+@\w+\.\w+>", args[1], re.IGNORECASE)
  if(checkSyntax):
    s.send("252 - VRFY'ed user \n".encode())
  else:
    s.send("450 4.1.2 Recipient address rejected: Domain not found \n".encode())

def RSET(args, s, client_address, state):
  fileName = str(state['file'] + '.txt')
  with open(fileName) as f:
    first_line = f.readline()
  open(fileName, 'w').close()
  with open(fileName, 'a') as the_file:
    the_file.write(first_line)
  state['MAIL'] = False
  state['RCPT'] = False
  s.send("250 OK \n".encode())

def findMXServer(email):
  domain = re.search("@[\w.]+", email)
  domain = domain.group()
  domain = domain[1:]
  try:
    mailExchangeServers = dns.resolver.query(domain, 'MX')
  except:
    print("no domain found \n")
    return
  lowestPref = ""
  pref = mailExchangeServers[0].preference
  for rdata in mailExchangeServers:
    if rdata.preference <= pref:
      lowestPref = rdata.exchange.__str__()
  lowestPref = lowestPref[:-1]
  return lowestPref

def relayData(client_address, state):
  filename = str(client_address) + '.txt'

  HOST = findMXServer(state['recipient'])

  if HOST:
    PORT = 25
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.connect((HOST, PORT))
    data = s.recv(1024)
    print('Received', repr(data))
    with open(filename) as fp:
      for line in fp:
        print('sent', repr(line))
        s.sendall(line.encode())
        if line == ".\r\n":
          data = s.recv(1024)
          print('Received', repr(data))
          answer = data.split(" ")
          if answer[0] != "250":
            filePath = os.path.realpath(filename)
            folderPath = os.path.join('errors', os.path.basename(filePath))
            shutil.copy(filename, folderPath)
    os.remove(filename)
  else:
    print("Host not found \n")
    filePath = os.path.realpath(filename)
    folderPath = os.path.join('errors', os.path.basename(filePath))
    shutil.copy(filename, folderPath)


def closeAndClean(s, state):
  state['loop'] = False
  s.close()
  if state['completedTransaction'] == False:
    fileName = str(state['file']) + '.txt'
    os.remove(fileName)


def recieveData(s, state):
    bufferSize = 4096
    buffer = (s.recv(bufferSize)).decode()
    buffering = True
    while buffering:
      if "\r\n.\r\n" in buffer:
          return buffer
      else:
          more = (s.recv(4096)).decode()
          if not more:
              buffering = False
          else:
              buffer += more
    return buffer

dispatch = {
    'helo': HELO,
    'mail': MAIL,
    'rcpt': RCPT,
    'data': DATA,
    'quit': QUIT,
    'vrfy': VRFY,
    'rest': RSET,
    'noop': NOOP
}

def process_network_command(command, args, s, client_address, state):
  command = command.lower()
  try:
    dispatch[command](args, s, client_address, state)
  except KeyError:
    s.send("502 5.5.2 Error: command not recognized \n".encode())

def linesplit(s, state):
  try:
    s.settimeout(300)
    buffer = (s.recv(4096)).decode()
    print(buffer, type(buffer))
    s.settimeout(None)
    buffering = True
    while buffering:
      if buffer == "STOP":
        s.send("500 5.5.2 Error: bad syntax \n".encode())
      if "\n" in buffer:
          (line, buffer) = buffer.split("\n", 1)
          return line
      else:
          more = (s.recv(4096)).decode()
          if not more:
              buffering = False
          else:
              buffer += more
  except socket.timeout:
    closeAndClean(s, state)

def handleClient(s, client_address):
  state = {
  'HELO': False,
  'MAIL': False,
  'RCPT': False,
  'loop': True,
  'data': False,
  'recipient': "",
  'file':0,
  'domain': "",
  'completedTransaction': False
  }
  try:
    s.send("220 SMTP Nour 1.0 \n".encode())
    print(">> ",sys.stderr, 'connection from', client_address)
    while state['loop']:
        lines = linesplit(s, state)
        if not(lines is None):
            args = lines.split()
        else:
            args = "EMPTY EMAIL".split()
        if len(args) > 0:
          process_network_command(args[0], args, s, client_address, state)
  finally:
      s.close()

def main():
  print(sys.argv)
  sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
  sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
  server_address = (sys.argv[1], 25)
  print(">> ",sys.stderr, 'starting up on %s port %s' % server_address)
  sock.bind(server_address)
  sock.listen(0)

  while True:
      print(">> ",sys.stderr, 'waiting for a connection')
      connection, client_address = sock.accept()
      if connection:
          try:
              _thread.start_new_thread(handleClient, (connection,client_address))
          except KeyboardInterrupt:
              break

if __name__== "__main__":
  main()
