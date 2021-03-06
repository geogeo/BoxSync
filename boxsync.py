#!/usr/bin/python
import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
import logging
import boxdotnet
import os
import ConfigParser
import pickle
import atexit
import sys
from string import maketrans
import pycurl
import hashlib
API_KEY='ro7mkd0yge1d2ah6gupyet80cal7cyop'#BoxSyncClient
AUTH_TOKEN=''
BOX_FOLDER='/TEST'
SYNC_FOLDER=''
SHARE = ''
CONFIG=None
BOX=None
ACDATA=None
LCDATA={}
BOX_FOLDER_ID=''
class BoxError(Exception):
    """Exception class for errors received from Facebook."""
    pass

def download(box_cwd,src):
    BOX.download(src,AUTH_TOKEN,ACDATA[box_cwd]['id'])
    LCDATA[box_cwd]={}
    rs=BOX.get_file_info(
            file_id=ACDATA[box_cwd]['id'],
            api_key=API_KEY,
            auth_token=AUTH_TOKEN)
    logging.debug(rs.status[0].elementText)
    LCDATA[box_cwd]['id']=rs.info[0].file_id[0].elementText
    LCDATA[box_cwd]['updated']=os.path.getmtime(src)
    LCDATA[box_cwd]['sync']=True
    logging.info("[uploaded] %s to %s", src, box_cwd)
def upload(box_cwd,src,parent):
    if not ACDATA.has_key(parent):
        create_folder(ACDATA,parent)
    rs=BOX.upload(
        filename=src.encode('utf-8'),
        folder_id=ACDATA[parent]['id'],
        share=SHARE,
        api_key=API_KEY,
        auth_token=AUTH_TOKEN)
    status = rs.status[0].elementText
    if status =='upload_ok':
        ACDATA[box_cwd]={}
        ACDATA[box_cwd]['id']=rs.files[0].file[0]['id']
        ACDATA[box_cwd]['parent']=rs.files[0].file[0]['folder_id']
        rs=BOX.get_file_info(
            file_id=ACDATA[box_cwd]['id'],
            api_key=API_KEY,
            auth_token=AUTH_TOKEN)
        logging.debug(rs.status[0].elementText)
        ACDATA[box_cwd]['updated']=rs.info[0].file_id[0].elementText
        LCDATA[box_cwd]={}
        LCDATA[box_cwd]['id']=ACDATA[box_cwd]['id']
        LCDATA[box_cwd]['updated']=os.path.getmtime(src)
        LCDATA[box_cwd]['sync']=True
        logging.info("[uploaded] %s to %s", src, box_cwd)
        
    else:
        logging.warning(status)  
def create_folder(ACDATA,dir):
    parent,base=os.path.split(dir)
    if not ACDATA.has_key(parent):
        create_folder(ACDATA,parent)
    rs=BOX.create_folder(
        name=os.path.basename(dir),
        parent_id=ACDATA[parent]['id'],
        share=SHARE,
        api_key=API_KEY,
        auth_token=AUTH_TOKEN)
    status = rs.status[0].elementText
    if status =='create_ok':
        ACDATA[dir]={}
        ACDATA[dir]['id']=rs.folder[0].folder_id[0].elementText
        ACDATA[dir]['parent']=rs.folder[0].parent_folder_id[0].elementText

        logging.info("created Dir %s", dir)
    else:
        logging.warning(status)
    
        
class SyncEventHandler(FileSystemEventHandler):

    modiset=set()
    tomodi=set()
    def on_deleted(self, event):
        """Called when a file or directory is deleted.
        :param event: Event representing file/directory deletion.
        :type event: :class:`DirDeletedEvent` or :class:`FileDeletedEvent` """
        logging.debug('---------DELETING or RENAMING FILE-%s----------',event.src_path)
        global ACDATA
        """Called when a file or a directory is moved or renamed.

        :param event:
            Event representing file/directory movement.
        :type event:
            :class:`DirMovedEvent` or :class:`FileMovedEvent`
        """
        super(SyncEventHandler, self).on_deleted(event)
        cwd = event.src_path.replace(SYNC_FOLDER,'').decode('utf-8')
        box_cwd=BOX_FOLDER+cwd
        if os.path.basename(box_cwd)[0]=='.':
            return
        if not event.is_directory:
            self.modiset.add(box_cwd)
        what = 'directory' if event.is_directory else 'file'
        target='folder' if event.is_directory else 'file'
        logging.info("Deleting %s %s", what, cwd)
        logging.debug(ACDATA)
        logging.debug(box_cwd)
        try:
            rs = BOX.delete(
            target=target,
            target_id=ACDATA[box_cwd]['id'],
            api_key=API_KEY,
            auth_token=AUTH_TOKEN)
            status = rs.status[0].elementText
            if status =='s_delete_node':
                ACDATA.pop(box_cwd)
                LCDATA.pop(box_cwd)
                logging.info("Deleted %s",box_cwd)
            else:
                logging.warning(status)
        except KeyError,e:
            print 'KeyError',e
            
    def on_modified(self, event):
        """Called when a file or directory is modified.
        :param event: Event representing file/directory modification.
        :type event: :class:`DirModifiedEvent` or :class:`FileModifiedEvent` """
        super(SyncEventHandler, self).on_modified(event)
        
        cwd = event.src_path.replace(SYNC_FOLDER,'').decode('utf-8')
        what = 'directory' if event.is_directory else 'file'
        box_cwd=BOX_FOLDER+cwd
        if os.path.basename(box_cwd)[0]=='.':
            return
        if not event.is_directory:
            # logging.debug(self.modiset)
            if box_cwd in self.modiset:
                logging.debug("[already modi] %s %s", what, self.modiset)
                self.modiset.clear()
            else:
                logging.debug('[to modi] %s',box_cwd)
                self.on_created(event)
                self.modiset.add(box_cwd)
            
            #compare file mod time
            
        
    def on_created(self, event):
        global ACDATA
        
        scr=event.src_path.decode('utf-8')
        super(SyncEventHandler, self).on_created(event)
        cwd = event.src_path.replace(SYNC_FOLDER,'').decode('utf-8')
        box_cwd=BOX_FOLDER+cwd
        if os.path.basename(box_cwd)[0]=='.':
            return
        if not event.is_directory:
            self.modiset.add(box_cwd)
        what = 'directory' if event.is_directory else 'file'
        
        try:
            if event.is_directory:
                logging.info("Uploading %s: %s", what, cwd)
                create_folder(ACDATA,box_cwd)
            elif  os.path.basename(cwd)[0]!='.':
                logging.info("Uploading %s: %s", what, cwd)
                # print type(event.src_path),event.src_path
                parent,base=os.path.split(box_cwd)
                upload(box_cwd,src,parent)
                    
        except KeyError,e:
            print 'KeyError',e
        
        
    def on_moved(self, event):
        """Called when a file or a directory is moved or renamed.

        :param event:
            Event representing file/directory movement.
        :type event:
            :class:`DirMovedEvent` or :class:`FileMovedEvent`
        """
        try:
            
            global ACDATA

            super(SyncEventHandler, self).on_moved(event)
            cwd = event.src_path.replace(SYNC_FOLDER,'').decode('utf-8')
            box_cwd=BOX_FOLDER+cwd
            dest= event.dest_path.replace(SYNC_FOLDER,'').decode('utf-8')
            box_dest=BOX_FOLDER+dest
            parent,base = os.path.split(box_dest)
            logging.debug(parent)
            if os.path.basename(box_cwd)[0]=='.' or not ACDATA.has_key(os.path.split(box_dest)[0]):
                return
            what = 'directory' if event.is_directory else 'file'
            target='folder' if event.is_directory else 'file'
            if not event.is_directory:
                self.modiset.add(box_cwd)
            if os.path.split(event.src_path)[0]==os.path.split(event.dest_path)[0]:
                # rename

                logging.info("Renaming %s %s to %s", what, cwd,dest)
                rs = BOX.rename(
                    target=target,
                    target_id=ACDATA[box_cwd]['id'],
                    new_name=base,
                    api_key=API_KEY,
                    auth_token=AUTH_TOKEN)
                status = rs.status[0].elementText
                if status =='s_rename_node':
                    ACDATA[box_dest]=ACDATA.pop(box_cwd)
                    LCDATA[box_dest]=LCDATA.pop(box_cwd)
                    logging.info("Renamed Dir %s to %s",box_cwd,box_dest)
                else:
                    logging.warning(status)
            else:
                # move

                logging.info("Moving %s %s to %s", what, cwd,dest)
                rs=BOX.move(
                    target=target,
                    target_id=ACDATA[box_cwd]['id'],
                    destination_id=ACDATA[parent]['id'],
                    api_key=API_KEY,
                    auth_token=AUTH_TOKEN)
                status = rs.status[0].elementText
                if status =='s_move_node':
                    ACDATA[box_dest]=ACDATA.pop(box_cwd)
                    LCDATA[box_dest]=LCDATA.pop(box_cwd)
                    logging.info("Moved Dir %s to %s",box_cwd,box_dest)
                else:
                    logging.warning(status)
            if target=='folder':
                actree = BOX.get_account_tree(api_key=API_KEY,auth_token=AUTH_TOKEN,folder_id=BOX_FOLDER_ID,params=['simple'])
                logging.info(actree.status[0].elementText)
                ACDATA = _updata(actree.tree,'0',{},'/')
                LCDATA = indexing()
                logging.info('reindex')
        except KeyError,e:
            print 'KeyError',e
            
def _updata(xml,id,data,prefix):  
    for item in xml:
        parent=prefix
        if item.elementName=='folder':
            data[prefix+item['name']]={}
            data[prefix+item['name']]['id']=item['id']
            data[prefix+item['name']]['parent']=id
            data[prefix+item['name']]['folder']=True
            parent=''.join([prefix,item['name']])+'/'
            try:
                _updata(item.folders[0].folder,item['id'],data,parent)
            except:
                pass
            try:
                _updata(item.files[0].file,item['id'],data,parent)
            except:
                pass
        if item.elementName=='file':
            data[prefix+item['file_name']]={}
            data[prefix+item['file_name']]['id']=item['id']
            data[prefix+item['file_name']]['parent']=id
            data[prefix+item['file_name']]['updated']=item['updated']
            data[prefix+item['file_name']]['share']=item['shared']
            data[prefix+item['file_name']]['folder']=False
    return data

def full_sync():
    acset=set(ACDATA.keys())
    global LCDATA
    for top, dirs, files in os.walk(SYNC_FOLDER):
        for nm in files:
            path = os.path.join(top,nm).decode('utf-8')
            box_path  = BOX_FOLDER+path.replace(SYNC_FOLDER,'')
            if nm[0]=='.' or os.path.isdir(path):
                continue
            if ACDATA.has_key(box_path):#compare mod time
                acset.remove(box_path)
                print ACDATA[box_path],path
                if os.path.getmtime(path)-float(LCDATA[box_path]['updated'])<0:
                    logging.debug( 'download %s',path)
                    download(box_path,path)
                    # BOX.download(path,AUTH_TOKEN,ACDATA[box_path]['id'])
                elif os.path.getmtime(path)-float(LCDATA[box_path]['updated'])>0:
                    logging.debug('upload %d %s',os.path.getmtime(path)-float(LCDATA[box_path]['updated']),path)
                    upload(box_path,path,os.path.split(box_path)[0])
            else:
                if LCDATA.has_key(box_path):
                    if not LCDATA[box_path]['sync']:
                         upload(box_path,path,os.path.split(box_path)[0])
                    logging.debug('server deleted %s',path)
                else:
                    logging.debug('new in local %s',path)
                    upload(box_path,path,os.path.split(box_path)[0])
            
    for bxf in acset:
        path = SYNC_FOLDER+bxf.replace(BOX_FOLDER,'')
        parent,base = os.path.split(path)
        if ACDATA[bxf]['folder']:continue
        if not  os.path.isdir(path):
            if not os.path.exists(path):
                if LCDATA.has_key(bxf):
                    logging.debug('local deleted %s',bxf)
                    print 'Do you want to delete %s on server as well?[Y/n]' % bxf
                else:
                    logging.debug('server new %s',bxf)
                    logging.debug('https://www.box.net/api/1.0/download/'+AUTH_TOKEN+'/'+ACDATA[bxf]['id'])
                    if not os.path.exists(parent):
                        os.makedirs(parent)
                    download(bxf,path)
                    # BOX.download(path,AUTH_TOKEN,ACDATA[bxf]['id'])
def indexing():
    newdata={}
    for top, dirs, files in os.walk(SYNC_FOLDER):
        for nm in files:
            if nm[0]!='.':
                path = os.path.join(top,nm)
                logging.debug('indexing %s',path)
                box_path  = BOX_FOLDER+path.replace(SYNC_FOLDER,'').decode('utf-8')
                if box_path in ACDATA:
                    newdata[box_path]=ACDATA[box_path]
                    newdata[box_path]['updated']=os.path.getmtime(path)
                    newdata[box_path]['sync']=False
                    continue
                newdata[box_path]={}
                newdata[box_path]['updated']=os.path.getmtime(path)
                newdata[box_path]['sync']=False
    return newdata

    

if __name__ == "__main__":
    
    CONFIG = ConfigParser.RawConfigParser()#allow_no_value=True)
    c=CONFIG.read('config.cfg')
    default_config="""
    [UserSetting]
    sync_path = ~/BoxSync
    box_path = /TEST
    log = 20
    login = false
    auth_token = nosetyet
    share = 0
    """
    

    if len(c)==0:
        CONFIG.readfp(StringIO(default_config))
        with open('config.cfg', 'wb') as configfile:
            CONFIG.write(configfile)
        # CO# NFIG.read('config.cfg')
    SYNC_FOLDER= CONFIG.get('UserSetting','sync_path')
    SYNC_FOLDER = os.path.expanduser(SYNC_FOLDER)
    BOX_FOLDER = CONFIG.get('UserSetting','box_path')
  
    SHARE =  CONFIG.get('UserSetting','share')
    BOX= boxdotnet.BoxDotNet()
    logging.basicConfig(level=int(CONFIG.get('UserSetting','log')))
    # logging.debug(AUTH_TOKEN)
    if not CONFIG.getboolean('UserSetting','login'):
        ticket = BOX.login(API_KEY)
        # logging.debug('ticket2='+ticket)
        print 'Login to Auth BoxSyn App from the Page Just Popup.'
        while True:
            done_auth = raw_input('Did you Login?[Y/n]')
            if done_auth=='y' or done_auth=='':
                print 'Login sucessfully! Now you can Sync your files in folder=>'+SYNC_FOLDER
                rsp = BOX.get_auth_token(api_key=API_KEY, ticket=ticket)
                if rsp.status[0].elementText=='get_auth_token_ok':
                    AUTH_TOKEN = rsp.auth_token[0].elementText
                    CONFIG.set('UserSetting','login','true')
                    CONFIG.set('UserSetting','auth_token',AUTH_TOKEN)
                    with open('config.cfg', 'wb') as configfile:
                        CONFIG.write(configfile)
                    break
                else:
                    logging.warning(rsp.status[0].elementText)
                    continue

            elif done_auth=='n':
                print 'Bye then~'
                sys.exit(0)
            else:
                print r'input only "y" or "n" or just press Enter plz.'
    else:
        AUTH_TOKEN=CONFIG.get('UserSetting','auth_token')
    try:
        logging.info('loaded data')
        data_file = open('.data.p','rb')
        ACDATA=pickle.load(data_file)
        logging.info('loaded data')
       
    except:
        
        actree = BOX.get_account_tree(api_key=API_KEY,auth_token=AUTH_TOKEN,folder_id=0,params=['simple'])
        logging.info(actree.status[0].elementText)
        print actree.tree[0].elementName
    
        ACDATA = _updata(actree.tree,'0',{},'')
        logging.debug(ACDATA)
        with open('.data.p','wb') as data_file:
            pickle.dump(ACDATA,data_file)
        
    BOX_FOLDER_ID=ACDATA[BOX_FOLDER]['id']
    actree = BOX.get_account_tree(api_key=API_KEY,auth_token=AUTH_TOKEN,folder_id=BOX_FOLDER_ID,params=['simple'])
    ACDATA = _updata(actree.tree,'0',{},'/')
    logging.debug(ACDATA)

    # firstsync=False
    try:
        logging.info('indexing sync folers')
        LCDATA = pickle.load(open('.index.p','rb'))
        logging.info('read indexing file')
    except :
        LCDATA = indexing()
        # firstsync=True
        with open('.index.p','wb') as data_file:
            pickle.dump(LCDATA,data_file)
    logging.debug(LCDATA)
    logging.info('completed indexing')

    
    #     actree = BOX.get_account_tree(api_key=API_KEY,auth_token=AUTH_TOKEN,folder_id=0,params=['nozip','simple'])
    #     logging.info(actree.status[0].elementText)
    #     ACDATA = _updata(actree.tree[0].folder[0].folders[0].folder,'0',{},'/')
    #     print ACDATA
    #     with open('data.p','wb') as data_file:
    #         pickle.dump(ACDATA,data_file)

    
    
    event_handler = SyncEventHandler()
    full_sync()
    logging.info('Finished Full Sync! Leavit along so any change in your folder can be sync to Box!')
    observer = Observer()
    observer.schedule(event_handler, path=SYNC_FOLDER, recursive=True)
    observer.start()
    try:
        while True:
             #---------FULL SYNC ------------------ every five min
            
            time.sleep(300)
            logging.debug('5 min')
    except KeyboardInterrupt:
        print 'Saving'
        with open('.data.p','wb') as data_file:
            pickle.dump(ACDATA,data_file)
            print 'Saved'
        with open('.index.p','wb') as index_file:
            pickle.dump(LCDATA,index_file)
            print 'index file Saved'
        print 'Bye!'
        observer.stop()

    except KeyError:
        logging.warning(KeyError)
    observer.join()
