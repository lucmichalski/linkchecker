# -*- coding: iso-8859-1 -*-
# Copyright (C) 2004-2009 Bastian Kleineidam
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.
"""docutils HTML writer with navigation placeholder and information"""

from docutils import writers, nodes, utils
from docutils.writers import html4css1
from docutils.parsers.rst.directives.html import MetaBody

import sys
import os
import re
try:
    import Image # check for the Python Imaging Library
except ImportError:
    Image = None


class NavInfo (object):
    """store nav info"""

    def __init__ (self, name, level, visible=True, order=sys.maxint):
        self.name = name
        self.level = level
        self.visible = visible
        self.order = order

    def export (self):
        """return machine-parseable navigation information, suitable
           for config files"""
        return "\n".join([
          "name = %r" % self.name,
          "level = %d" % self.level,
          "visible = %s" % self.visible,
          "order = %d" % self.order,
        ])

    def __str__ (self):
        return "[%d]%r %s order=%d"%\
          (self.level, self.name,
           (self.visible and "visible" or ""), self.order)


class Writer (html4css1.Writer):
    """writer using custom nav class"""

    def __init__ (self):
        writers.Writer.__init__(self)
        self.translator_class = HTMLFileNavTranslator


class FixedHTMLTranslator (html4css1.HTMLTranslator):

    def visit_image (self, node):
        """
        Like super.visit_image(), but with align="middle" enforcement.
        """
        atts = {}
        atts['src'] = node['uri']
        if node.has_key('width'):
            atts['width'] = node['width']
        if node.has_key('height'):
            atts['height'] = node['height']
        if node.has_key('scale'):
            if Image and not (node.has_key('width')
                              and node.has_key('height')):
                try:
                    im = Image.open(str(atts['src']))
                except (IOError, # Source image can't be found or opened
                        UnicodeError):  # PIL doesn't like Unicode paths.
                    pass
                else:
                    if not atts.has_key('width'):
                        atts['width'] = str(im.size[0])
                    if not atts.has_key('height'):
                        atts['height'] = str(im.size[1])
                    del im
            for att_name in 'width', 'height':
                if atts.has_key(att_name):
                    match = re.match(r'([0-9.]+)(\S*)$', atts[att_name])
                    assert match
                    atts[att_name] = '%s%s' % (
                        float(match.group(1)) * (float(node['scale']) / 100),
                        match.group(2))
        style = []
        for att_name in 'width', 'height':
            if atts.has_key(att_name):
                if re.match(r'^[0-9.]+$', atts[att_name]):
                    # Interpret unitless values as pixels.
                    atts[att_name] += 'px'
                style.append('%s: %s;' % (att_name, atts[att_name]))
                del atts[att_name]
        if style:
            atts['style'] = ' '.join(style)
        atts['alt'] = node.get('alt', atts['src'])
        if (isinstance(node.parent, nodes.TextElement) or
            (isinstance(node.parent, nodes.reference) and
             not isinstance(node.parent.parent, nodes.TextElement))):
            # Inline context or surrounded by <a>...</a>.
            suffix = ''
        else:
            suffix = '\n'
        if node.has_key('align'):
            if node['align'] == 'center':
                if suffix:
                    # "align" attribute is set in surrounding "div" element.
                    self.body.append('<div align="center" class="align-center">')
                    self.context.append('</div>\n')
                    suffix = ''
                else:
                    atts['align'] = 'middle'
                    self.context.append('')
            else:
                # "align" attribute is set in "img" element.
                atts['align'] = node['align']
                self.context.append('')
            atts['class'] = 'align-%s' % node['align']
        else:
            self.context.append('')
        self.body.append(self.emptytag(node, 'img', suffix, **atts))


class HTMLNavTranslator (FixedHTMLTranslator):
    """ability to parse navigation meta info"""

    def __init__ (self, document):
        html4css1.HTMLTranslator.__init__(self, document)
        name = os.path.basename(self.settings._destination)
        name = os.path.splitext(name)[0].capitalize()
        self.nav_info = NavInfo(name, 0)
        self.parse_meta_nav(document)
        self.process_meta_nav()

    def parse_meta_nav (self, document):
        # look for meta tags in document with nav info
        i = document.first_child_matching_class(MetaBody.meta)
        while i is not None:
            meta = document[i]
            if meta.attributes.get('name', '').startswith('navigation.'):
                self.add_meta_nav(meta.attributes)
            i = document.first_child_matching_class(MetaBody.meta, start=i+1)

    def process_meta_nav (self):
        pass

    def add_meta_nav (self, attributes):
        navattr = attributes['name'][11:]
        val = attributes['content']
        if navattr=='order':
            self.nav_info.order = int(val)
        elif navattr=='name':
            self.nav_info.name = val
        elif navattr=='visible':
            self.nav_info.visible = val.lower() not in ['0', 'false']
        else:
            print >> sys.stderr, "unknown navigation attr", repr(navattr)


class HTMLFileNavTranslator (HTMLNavTranslator):
    """write .nav files and put navigation placeholder in html file"""

    def __init__ (self, document):
        HTMLNavTranslator.__init__(self, document)
        self.body_prefix = [
            self.get_favicon(),
            self.get_nav_css(),
            self.get_topframe_bashing(),
            '</head>\n<body>\n',
            self.get_nav_placeholder(),
        ]
        self.body_suffix = [
            "</body>\n</html>\n",
        ]

    def get_topframe_bashing (self):
        return """<script type="text/javascript">
<!--
window.onload = function() {
  if (top.location != location) {
    top.location.href = document.location.href;
  }
}
// -->
</script>
"""

    def get_nav_placeholder (self):
        return "<!-- bfknav -->\nImagine a navigation\n<!-- /bfknav -->\n"

    def process_meta_nav (self):
        prefix = os.path.splitext(self.settings._destination)[0]
        nav = file(prefix+".nav", 'w')
        nav.write("# generated by htmlnav.py, do not edit\n")
        nav.write(self.nav_info.export())
        nav.write("\n")
        nav.close()

    def get_nav_css (self):
        p = self.settings.stylesheet_path.split("/")[:-1]
        p.append("navigation.css")
        p = "/".join(p)
        p = utils.relative_path(self.settings._destination, p)
        link = html4css1.HTMLTranslator.stylesheet_link
        return link % p

    def get_favicon (self):
        p = self.settings.stylesheet_path.split("/")[:-1]
        p.append("favicon.png")
        p = "/".join(p)
        p = utils.relative_path(self.settings._destination, p)
        return '<link rel="shortcut icon" type="image/x-icon" href="%s" />\n' % p
