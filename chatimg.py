#!/usr/bin/env python
# -*- coding: utf-8

##Reference code by:
##

# This is free and unencumbered software released into the public domain.
#
# Anyone is free to copy, modify, publish, use, compile, sell, or
# distribute this software, either in source code form or as a compiled
# binary, for any purpose, commercial or non-commercial, and by any
# means.
#
# In jurisdictions that recognize copyright laws, the author or authors
# of this software dedicate any and all copyright interest in the
# software to the public domain. We make this dedication for the benefit
# of the public at large and to the detriment of our heirs and
# successors. We intend this dedication to be an overt act of
# relinquishment in perpetuity of all present and future rights to this
# software under copyright law.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
# EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
# MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
# IN NO EVENT SHALL THE AUTHORS BE LIABLE FOR ANY CLAIM, DAMAGES OR
# OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE,
# ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR
# OTHER DEALINGS IN THE SOFTWARE.


#
# chatimg.py
# Post images into mumble chat through data injection, creates thumbnails for images that are too large.
#
from PIL import Image
import StringIO

from mumo_module import (commaSeperatedIntegers,
                         MumoModule)

import urllib2
import base64
import re
import ImageFile


class chatimg(MumoModule):
    default_config = {'chatimg':(
                                ('servers', commaSeperatedIntegers, []),
                                ('keyword', str, '!img'),
                                ('shebang_required', int, 1),
                                ('max_width', int, 500),
                                ('max_height', int, 1000),
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
        self.keyword = self.cfg().chatimg.keyword

    def connected(self):
        """Callback for connection, sets up registration as a handler to all server methods.
        """
        manager = self.manager()
        self.log().debug("Register [%s] callbacks", self.name())

        manager.subscribeServerCallbacks(self, self.cfg().chatimg.servers or manager.SERVERS_ALL)

    def readImageDataPerByte(self, open_url):
        """Utility method for reading a an image, reads 1kb at a time.

        :param open_url:  urlinfo opened urllib2 object for the image url.
        :return: 1024 byte data set
        """
        data = open_url.read(1024)
        while data:
            yield data
            data = open_url.read(1024)

    def getDataFromImage(self, open_url, img_info=None):
        """Attains header information from img liburl

        :param open_url: urlinfo opened urllib2 object for the image url.
        :param img_info: ImageInfo
        :return:
        """

        img_parser = ImageFile.Parser()

        for block_buf in self.readImageDataPerByte(urllib2.urlopen(open_url.geturl())):
            img_parser.feed(block_buf)
            if img_parser.image:
                img_info.width, img_info.height = img_parser.image.size
                return img_info

    def getImageStats(self, open_url):
        """Function verifies that the passed url is an image, and returns a struct containing it's data.

        :param open_url: urlinfo opened urllib2 object for the image url.
        :return: ImageInfo containing the images parameters or None if the url was not an image.
        """
        ret_image_info = None
        if "image" in open_url.headers.get("content-type"):
            ret_image_info = self.ImageInfo()

            ret_image_info.size = open_url.headers.get("content-length") or None
            if ret_image_info.size:
                ret_image_info.size = int(ret_image_info.size)
            self.getDataFromImage(open_url, ret_image_info)

        return ret_image_info

    def injectImage(self, img_info, open_url):
        """Injects an image into an HTML coded string.

        :param img_info: ImageInfo for this image.
        :param open_url: the liburl2 opened url of the image to be injected.
        :return: HTML string containing the injected image.
        """
        injected_img = None

        if img_info.size/1024 < 256:
            encoded = base64.b64encode(open_url.read())
            injected_img = ('<img src="data:image/jpeg;charset=utf-8;base64,' +
                            str(encoded) +
                            '" %s />' % self.getModifiers(img_info))
        else:
            image = Image.open(StringIO.StringIO(open_url.read()))
            image.thumbnail((self.cfg().chatimg.max_width, self.cfg().chatimg.max_height), Image.ANTIALIAS)
            trans = StringIO.StringIO()
            image.save(trans, format="JPEG")
            encoded = base64.b64encode(trans.getvalue())
            injected_img = ('<img src="data:image/jpeg;charset=utf-8;base64,' +
                            str(encoded) +
                            '"  />')

        return injected_img

    def getModifiers(self, img_info):
        """ If the image is greater then the limits for images set in config, generates an html style descriptor.

        :param img_info: ImageInfo - the full img_info for this image.
        :return: str containing the modifier needed in order to resize the image in html, or blank if no resizing
        is required.
        """
        modifiers = ""
        width_percent_reduction = 0
        height_percent_reduction = 0
        max_width = float(self.cfg().chatimg.max_width)
        max_height = float(self.cfg().chatimg.max_height)
        if max_width and img_info.width > max_width:
            width_percent_reduction = (img_info.width / max_width) - 1.0
        if max_height and img_info > max_height:
            height_percent_reduction = (img_info.height / max_height) - 1.0

        if width_percent_reduction > 0 and width_percent_reduction > height_percent_reduction:
            modifiers = " width=\"%s\" " % max_width
        elif height_percent_reduction > 0:
            modifiers = " height=\"%d\" " % max_height

        return modifiers
    
    def userTextMessage(self, server, user, message, current=None):
        """Callback for when a user sends any sort of text message to the mumble server.

        :param server: server from which the callback was called
        :param user: user whom entered the message
        :param message: the message data for the sent message []
        :param current: unused in this instance, needed for overwriting
        """
        shebang_used = False
        msg = None

        if message.text.startswith(self.keyword):
            msg = message.text[len(self.keyword):].strip()
            shebang_used = True
        elif not self.cfg().chatimg.shebang_required:
            msg = message.text

        if msg:
            links = re.findall(r'href=[\'"]?([^\'" >]+)', msg)

            for link in links:
                msg = None
                try:
                    img = urllib2.urlopen(link)
                    img_info = self.getImageStats(img)

                    if img_info:
                        msg = '<a href="%s" >' % link
                        msg += self.injectImage(img_info, img)
                        msg += "</a>"
                    elif shebang_used:
                        msg = ("Image Posted by %s, isn't an image, or some odd format." % user.name)
                except urllib2.HTTPError:
                    if shebang_used:
                        msg = "Invalid URL linked by %s , cannot resolve" % user.name

                if msg:
                    server.sendMessageChannel(user.channel, False, msg)

    def __getattr__(self, item):
        """This is a bypass method for getting rid of all the callbacks that are not handled by this module.

        :param item: item that is being queried for
        :return: an unused callable attribute that does not do anything
        """
        def unused_callback(*args, **kwargs):
            pass
        return unused_callback
