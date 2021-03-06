"""
Python bindings for the Box.net API

Copyright (c) 2007 Thomas Van Machelen <thomas dot vanmachelen at gmail dot com>
Copyright (c) 2007 John Stowers <john dot stowers at gmail dot com>

Upload, handler and XMLNode code adapted from flickrapi:
Copyright (c) 2007 Brian "Beej Jorgensen" Hall

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
You may obtain a copy of the License at

http://www.apache.org/licenses/LICENSE-2.0

Unless required by applicable law or agreed to in writing, software
distributed under the License is distributed on an "AS IS" BASIS,
WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. 
See the License for the specific language governing permissions and 
limitations under the License. 

"""
import urllib
import urllib2
import mimetools
import mimetypes
import os
import sys
import logging
from xml.dom.minidom import parseString
import xml.dom
import pycurl
from StringIO import StringIO
import math
import zipfile

def draw_progress(percent):
    width=50
    marks = math.floor(width * (percent / 100.0))
    spaces = math.floor(width - marks)
    loader = '[' + ('=' * (int(marks)-1)) +'>'+ (' ' * int(spaces)) + ']'
    sys.stdout.write("%s %d%%\r" % (loader, percent))
    sys.stdout.flush()

    
def progress(download_t, download_d, upload_t, upload_d):
        # print "Total to download", download_t
    # print "Total downloaded", download_d
    
    if download_t != 0 and download_t!=download_d:
        percent = download_d/download_t*100
        draw_progress(percent)
    if upload_t !=0 and upload_t!=upload_d:
        percent = upload_d/upload_t*100
        draw_progress(percent)
        # Returning None implies that all bytes were written
	
def get_content_type(filename):
	return mimetypes.guess_type(filename)[0] or 'application/octet-stream'

########################################################################
# XML functionality
########################################################################

#-----------------------------------------------------------------------
class XMLNode:
    """XMLNode -- generic class for holding an XML node

    xmlStr = \"\"\"<xml foo="32">
    <name bar="10">Name0</name>
    <name bar="11" baz="12">Name1</name>
    </xml>\"\"\"

    f = XMLNode.parseXML(xmlStr)

    print f.elementName              # xml
    print f['foo']                   # 32
    print f.name                     # [<name XMLNode>, <name XMLNode>]
    print f.name[0].elementName      # name
    print f.name[0]["bar"]           # 10
    print f.name[0].elementText      # Name0
    print f.name[1].elementName      # name
    print f.name[1]["bar"]           # 11
    print f.name[1]["baz"]           # 12

    """

    def __init__(self):
        """Construct an empty XML node."""
        self.elementName=""
        self.elementText=""
        self.attrib={}
        self.xml=""

    def __setitem__(self, key, item):
        """Store a node's attribute in the attrib hash."""
        self.attrib[key] = item

    def __getitem__(self, key):
        """Retrieve a node's attribute from the attrib hash."""
        return self.attrib[key]

    #-----------------------------------------------------------------------
    @classmethod
    def parseXML(cls, xmlStr, storeXML=False):
        """Convert an XML string into a nice instance tree of XMLNodes.

        xmlStr -- the XML to parse
        storeXML -- if True, stores the XML string in the root XMLNode.xml
        """

        def __parseXMLElement(element, thisNode):
            """Recursive call to process this XMLNode."""
            thisNode.elementName = element.nodeName

            #print element.nodeName

            # add element attributes as attributes to this node
            for i in range(element.attributes.length):
                an = element.attributes.item(i)
                thisNode[an.name] = an.nodeValue

            for a in element.childNodes:
                if a.nodeType == xml.dom.Node.ELEMENT_NODE:

                    child = XMLNode()
                    try:
                        list = getattr(thisNode, a.nodeName)
                    except AttributeError:
                        setattr(thisNode, a.nodeName, [])

                    # add the child node as an attrib to this node
                    list = getattr(thisNode, a.nodeName);
                    #print "appending child: %s to %s" % (a.nodeName, thisNode.elementName)
                    list.append(child);

                    __parseXMLElement(a, child)

                elif a.nodeType == xml.dom.Node.TEXT_NODE:
                    thisNode.elementText += a.nodeValue

            return thisNode

        dom = parseString(xmlStr)

        # get the root
        rootNode = XMLNode()
        if storeXML: rootNode.xml = xmlStr

        return __parseXMLElement(dom.firstChild, rootNode)

class BoxDotNetError(Exception):
    """Exception class for errors received from Facebook."""
    pass
import webbrowser
import base64
class BoxDotNet(object):
    END_POINT = 'http://www.box.net/api/1.0/rest?'

    #The box.net return status codes are all over the show
    # method_name : return_value_that_is_ok
    RETURN_CODES = {
        'get_ticket'        :   'get_ticket_ok',
        'get_auth_token'    :   'get_auth_token_ok',
        'get_account_tree'  :   'listing_ok',
        'logout'            :   'logout_ok',
        'create_folder'     :   'create_ok',
        'upload'            :   'upload_ok',
        'delete'            :   's_delete_node'
    }

    def __init__(self, browser="firefox"):
        self.browser = browser

        self.__handlerCache={}

    #encodes the args and handles params[] supplied in a list
    @classmethod
    def __url_encode_params(cls, params={}):
    	if not isinstance(params, dict):
    		raise Exception("You must pass a dictionary!")
    	params_list = []
    	for k,v in params.items():
    		if isinstance(v, list): params_list.extend([(k+'[]',x) for x in v])
    		else:					params_list.append((k, v))
    	return urllib.urlencode(params_list)

    @classmethod
    def check_errors(cls, method, xml):
	pass
        # status = xml.status[0].elementText

        # if status == cls.RETURN_CODES[method]:
        #     return

        # raise BoxDotNetError ("Box.net returned [%s] for action [%s]" % (status, method))
    
    def login(self, api_key):
        # get ticket
        rsp = self.get_ticket (api_key=api_key)
        ticket = rsp.ticket[0].elementText
        # open url
        url = "http://www.box.net/api/1.0/auth/%s" % ticket
        #os.system('%s "%s"' % (self.browser, url))
        webbrowser.open(url)
        # get token
        # rsp = self.get_auth_token(api_key=api_key, ticket=ticket)
        #
	logging.debug('ticket='+ticket)
        return ticket

    def __getattr__(self, method, **arg):
        """
        Handle all box.net calls
        """
        if not self.__handlerCache.has_key(method):
            def handler(_self = self, _method = method, **arg):
                url = _self.END_POINT
                arg["action"] = _method
                postData = _self.__url_encode_params(params=arg)
                # print "--url---------------------------------------------"
                # print url
                # print "--postData----------------------------------------"
                # print postData
		logging.debug(url+postData)
                f = urllib.urlopen(url + postData)
                data = f.read()

                # print "--response----------------------------------------"
                
#                print data
                f.close()
                
                xml = XMLNode.parseXML(data, True)
		if method=='get_account_tree':
		    # logging.debug(xml.tree[0].elementText)
		    decode_data=base64.b64decode(xml.tree[0].elementText)
		    fp=StringIO(decode_data)
		    zfp=zipfile.ZipFile(fp,'r')
		    ftree=zfp.read(zfp.namelist()[0])
		    # logging.debug(ftree)
		    
		    xml.tree[0]=XMLNode.parseXML(ftree)
                #print ecode_data
                _self.check_errors(_method, xml) 
                return xml

            self.__handlerCache[method] = handler;

        return self.__handlerCache[method]

    #-------------------------------------------------------------------
    #-------------------------------------------------------------------

    def download(self,path,auth_token,file_id):
        ftw = open(path,'wb')
        c = pycurl.Curl()
        url='https://www.box.net/api/1.0/download/'+auth_token+'/'+file_id
        logging.debug(url)
        c.setopt(c.URL,url.encode('utf-8'))
        c.setopt(c.PROGRESSFUNCTION, progress)
        c.setopt(pycurl.WRITEFUNCTION, ftw.write)
        c.setopt(c.NOPROGRESS,0)
        # c.setopt(c.RETURNTRANSFER,False)
        c.perform()
        loader = '[' + ('=' * (49)) +'>'+ ']'
	sys.stdout.write("%s %d%%\r" % (loader, 100))
	sys.stdout.flush()
	sys.stdout.write("\n")
        c.close()
        ftw.close()
    def upload(self, filename, **arg):
        """
        Upload a file to box.net.
        """

        if filename == None:
            raise UploadException("filename OR jpegData must be specified")

        # verify key names
        for a in arg.keys():
            if a != "api_key" and a != "auth_token" and a != "folder_id" and a != 'share':
                sys.stderr.write("Box.net api: warning: unknown parameter \"%s\" sent to Box.net.upload\n" % (a))

        url = 'http://upload.box.net/api/1.0/upload/%s/%s' % (arg['auth_token'], arg['folder_id'])

	c = pycurl.Curl()
	
	c.setopt(c.URL,url.encode('utf-8'))
	# fp.close(
	c.setopt(c.HTTPPOST,[ ("file", filename), 
                      ("share", arg['share']), 
                      (filename, 
                                 (c.FORM_FILE, filename, 
                                  c.FORM_CONTENTTYPE, get_content_type(filename)))
                    ])
	c.setopt(c.PROGRESSFUNCTION, progress)
	storage = StringIO()
	c.setopt(pycurl.WRITEFUNCTION, storage.write)
	c.setopt(c.NOPROGRESS,0)
	c.perform()
	
	loader = '[' + ('=' * (49)) +'>'+ ']'
	sys.stdout.write("%s %d%%\r" % (loader, 100))
	sys.stdout.flush()
	sys.stdout.write("\n")
	c.close()
	rspXML=storage.getvalue()
	# print 'xml',self.rspXML
        return XMLNode.parseXML(rspXML)

