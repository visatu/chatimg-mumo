#!/usr/bin/env python
# -*- coding: utf-8

import StringIO

from mumo_module import (commaSeperatedIntegers,
                         commaSeperatedStrings,
                         MumoModule)

import urllib2
import base64
import re
import os
import random

try:
    import ImageFile
    import Image
except ImportError:
    from PIL import ImageFile
    from PIL import Image

class randimg(MumoModule):
    default_config = {'randimg':(
                                ('servers', commaSeperatedIntegers, []),
                                ('basedir', str, "."),
                                ('baselink', str, ""),
                                ('baserand', str, "truerand"),
                                ('keywords', commaSeperatedStrings, []),
                                ('max_width', int, 500),
                                ('max_height', int, 1000),
                                ('links', commaSeperatedStrings, [])
                                )
                    }

    class ImageInfo(object):
        """Class for storing image information.
            size = size of the image in bytes
            width = width of the image in pixels
            height = height of the image in pixels
        """
        def __init__(self,
                     size=None,
                     width=None,
                     height=None):
            self.size = size
            self.width = width
            self.height = height

    def __init__(self, name, manager, configuration = None):
        MumoModule.__init__(self, name, manager, configuration)
        self.murmur = manager.getMurmurModule()
        self.basedir = os.path.abspath(self.cfg().randimg.basedir)
        self.baselink = self.cfg().randimg.baselink
        self.baserand = self.cfg().randimg.baserand
        self.keywords = self.cfg().randimg.keywords
        self.links = self.cfg().randimg.links
        self.allimages = self.listAllImages()

    def connected(self):
        """Callback for connection, sets up registration as a handler to all server methods.
        """
        manager = self.manager()
        self.log().debug("Registered for [%s] callbacks", self.name)
        manager.subscribeServerCallbacks(self, self.cfg().randimg.servers or manager.SERVERS_ALL)

    def listAllImages(self):
        """
        Returns a list of all images within the configured keyword folders
        """
        self.log().debug("Listing all images..")
        all_images = []
        for keyword in self.keywords:
            dir = os.path.join(self.basedir, keyword)
            filenames = os.listdir(dir)
            for fname in filenames:
                all_images.append([keyword,fname])
        return all_images

    def readImageDataPerByte(self, open_url):
        """Utility method for reading a an image, reads 1kb at a time.
        :param open_url:  urlinfo opened urllib2 object for the image url.
        :return: 1024 byte data set
        """
        data = open_url.read(1024)
        while data:
            yield data
            data = open_url.read(1024)

    def getModifiers(self, img_info):
        """ If the image is greater then the limits for images set in config, generates an html style descriptor.
        :param img_info: ImageInfo - the full img_info for this image.
        :return: str containing the modifier needed in order to resize the image in html, or blank if no resizing
        is required.
        """
        modifiers = ""
        width_percent_reduction = 0
        height_percent_reduction = 0
        max_width = float(self.cfg().randimg.max_width)
        max_height = float(self.cfg().randimg.max_height)
        if max_width and img_info.width > max_width:
            width_percent_reduction = (img_info.width / max_width) - 1.0
        if max_height and img_info > max_height:
            height_percent_reduction = (img_info.height / max_height) - 1.0

        if width_percent_reduction > 0 and width_percent_reduction > height_percent_reduction:
            modifiers = " width=\"%s\" " % max_width
        elif height_percent_reduction > 0:
            modifiers = " height=\"%d\" " % max_height

        return modifiers
      
    def injectImage(self, img_info, image, path):
        """Injects an image into an HTML coded string.
        :param img_info: ImageInfo for this image.
        :param open_url: the liburl2 opened url of the image to be injected.
        :return: HTML string containing the injected image.
        """
        injected_img = None

        if img_info.size/1024 < 256:
            with open(path,"rb") as image_file:
                encoded = base64.b64encode(image_file.read())
            injected_img = ('<img src="data:image/jpeg;charset=utf-8;base64,' +
                            str(encoded) +
                            '" %s />' % self.getModifiers(img_info))
        else:
            image.thumbnail((self.cfg().randimg.max_width, self.cfg().randimg.max_height), Image.ANTIALIAS)
            trans = StringIO.StringIO()
            image.save(trans, format="PNG")
            encoded = base64.b64encode(trans.getvalue())
            injected_img = ('<img src="data:image/jpeg;charset=utf-8;base64,' +
                            str(encoded) +
                            '"  />')

        return injected_img

    def sendImage(self, img_path, keyword, filename, server, user):
        try:
            img = Image.open(img_path)
            # get image info
            img_info = self.ImageInfo()
            img_info.size = int(os.path.getsize(img_path))
            img_info.width, img_info.height = img.size
            if img_info:
                # If base link configured, use that as a link for the image
                if self.baselink.endswith('/'):
                    msg = '<a href="'+ self.baselink + keyword + '/' + filename + '">'
                    msg += self.injectImage(img_info, img, img_path)
                    msg += "</a>"
                elif self.baselink:
                    msg = '<a href="'+ self.baselink + '">'
                    msg += self.injectImage(img_info, img, img_path)
                    msg += "</a>"
                else:
                    msg = self.injectImage(img_info, img, img_path)
        except urllib2.HTTPError:
            msg = "AIJAI SATTUU"
        if msg:
            server.sendMessageChannel(user.channel, False, msg)

    def userTextMessage(self, server, user, message, current=None):
        """Callback for when a user sends any sort of text message to the mumble server.
        :param server: server from which the callback was called
        :param user: user whom entered the message
        :param message: the message data for the sent message []
        :param current: unused in this instance, needed for overwriting
        """
        # Pick a random image from the list of keyword folers in possible image folder. also get many number of file to get randome. also use baserand as keyword. also check al keyword to see: how many folder to chekc. also post a random image from the generations list.
        if message.text.lower().startswith('!' + self.baserand):
            # choose random image to post from list created at init.
            chosen = random.choice(self.allimages)
            keyword = chosen[0]
            filename = chosen[1]
            path = os.path.join(self.basedir, keyword, filename)
            self.sendImage(path, keyword, filename, server, user)
            return
        # Check for configured list of keywords
        for keyword in self.keywords:
            if message.text.lower().startswith("!" + keyword):
                # directory to search file from and file path
                dir = os.path.join(self.basedir, keyword)
                filename = random.choice(os.listdir(dir))
                path = os.path.join(self.basedir, keyword, filename)
                self.sendImage(path, keyword, filename, server, user)
                

    def __getattr__(self, item):
        """This is a bypass method for getting rid of all the callbacks that are not handled by this module.
        :param item: item that is being queried for
        :return: an unused callable attribute that does not do anything
        """
        def unused_callback(*args, **kwargs):
            pass
        return unused_callback