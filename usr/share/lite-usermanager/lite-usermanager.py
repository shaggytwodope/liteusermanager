#!/usr/bin/env python
#  liteusermanager
#
#  Copyright 2008 Michael Towers <gradgrind[at]online[dot]de>
#  Copyright 2016 Johnathan Jenkins <twodopeshaggy@gmail.com>
#
#  This program is free software; you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation; either version 2 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software
#  Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#  MA 02110-1301, USA.
#
#

import gtk
import os
import pwd
import grp
import crypt
import random
from subprocess import Popen, PIPE, STDOUT

# For running utilities as root:
import pexpect


helptext = ("""Linux Lite User Manager:

This program does not allow a normal user to change
his password unless he knows the root (administrator)
password. If you are running as a normal user and want
to change your password, open a terminal and run
'passwd'.

If you need more advanced user/group management
take a look at the man pages for 'useradd', 'usermod',
'userdel', 'groupadd', 'groupmod', 'groupdel', etc.

Here is a list of common groups and their functions.
This does not list every possible group name, please
seek help on the Linux Lite Site if your not sure.

    * audio = sound
    * camera = access to cameras.
    * disk = block devices not affected by other groups.
    * floppy = access to floppy drives.
    * kmem = rights to /dev/mem, /dev/port, /dev/kmem
    * log = access to log files in /var/log.
    * lp = printers
    * optical = access to dvd/cd drives.
    * network = right to use Networkmanager
    * power = right to suspend etc
    * root = root/admin power. Don't add your user to this.
    * scanner = scanners
    * locate = access to command updatedb
    * storage = access to external drives, flash drives, etc.
    * thinkpad = for thinkpad users accessing /dev/misc/nvram
    * tty = access to serial/USB devices like modems or handhelds
    * users = default users group (recommended)
    * vboxusers = right to use virtualbox
    * video = DRI/3D acceleration
    * vmware = right to execute vmware
    * wheel = right to use sudo (setup with visudo)
""")

abouttext = (
    '<b>Linux Lite User Manager Version 1.0-0040</b>\n'
    ' \n'
    '<b>Linux Lite User Manager</b> is a simple front-end for'
    ' user password and group management. It is'
    ' designed to work with <b>Linux Lite</b>, but should'
    ' work on most other linux systems.\n'
    ' \n'
    'This program was originally written for the <b>larch</b> project.\n'
    ' \n'
    'Modified for <b>Linux Lite</b> by:\n'
    '       Johnathan "ShaggyTwoDope" Jenkins\n'
    '       Jerry Bezencon'
    ' \n'
    '       <a href=\"http://www.linuxliteos.com\">www.linuxliteos.com</a>'
    ' \n'
    '\nThis is free software released under'
    ' <a href=\"https://www.gnu.org/licenses/gpl-2.0.html\">GPL2 License</a>')


class Luser(gtk.Window):
    def __init__(self):
        gtk.Window.__init__(self)
        self.set_title("Linux Lite User Manager")
        self.set_icon_from_file("/usr/share/pixmaps/liteusermanager.png")
        self.set_default_size(550, 300)
        self.connect("destroy", self.exit)
        self.set_border_width(3)
        self.password = None
        self.notebook = gtk.Notebook()
        self.add(self.notebook)
        self.notebook.set_tab_pos(gtk.POS_TOP)
        self.notebook.show_tabs = True
        self.notebook.show_border = False

        self.setup()

    def init(self):
        self.users = Users()
        self.notebook.append_page(self.users, gtk.Label("Users"))
        # self.notebook.append_page(Configure(), gtk.Label("Configure"))
        self.notebook.append_page(Help(), gtk.Label("Help"))
        self.notebook.append_page(About(), gtk.Label("About"))

        self.notebook.set_current_page(0)

    def setup(self):
        self.curuser = None

    def mainLoop(self):
        self.show_all()
        gtk.main()

    def exit(self, widget=None, data=None):
        self.pending()
        gtk.main_quit()

    def rootrun(self, cmd):
        """Run the given command as 'root'.
        Return a pair (completion code, output).
        """
        # If not running as 'root' use pexpect to use 'su' to run the command
        if (runninguser == 'root'):
            p = Popen(cmd, shell=True, stdout=PIPE, stderr=STDOUT)
            o = p.communicate()[0]
            return (p.returncode, o)
        else:
            if not self.password:
                pw = popupRootPassword()
                if (pw is None):
                    return (1, ("You cancelled the operation."))
                cc, mess = asroot('true', pw)
                if (cc != 0):
                    return (cc, mess)
                self.password = pw
            return asroot(cmd, self.password)

    def pending(self, user=None, force=False):
        """Handle pending changes to group membership for the current user.
        Should be called when the user is switched and when quitting the
        program. Can also be called by clicking the 'Apply' button.
        If 'force' is not True, a confirmation dialog will pop up.
        """
        if ((self.curuser in self.getUsers()) and (self.curuser != user)):

            nglist = self.users.grouplist.groupsChanged()
            if (nglist is not None):
                # Changes were requested, popup an apply confirmation dialog

                if force or confirm(("You have specified changes to the"
                                     " group memberships of user '%s'.\n\n"
                                     "Should these be applied?") %
                                    self.curuser):

                    glist = reduce(
                        (lambda a, b: a + ',' + b if a else b), nglist)
                    ccode, op = self.rootrun('usermod -G %s %s' %
                                             (glist, self.curuser))
                    if (ccode != 0):
                        error("The group memberships of user '%s'"
                              " could not be changed. Here is the system"
                              " message:\n\n %s") % (self.curuser, op)
                        return False

        self.enableApply(False)
        return True

    def apply(self, widget=None, data=None):
        self.pending(force=True)

    def setUsers(self):
        self.users.setUsers()

    def enableApply(self, on):
        self.users.enableApply(on)

    def changeUser(self, user):
        if self.pending(user):
            self.curuser = user
            self.users.displayUser(user)
            self.users.setGroups(user)
        else:
            self.users.resetUser(self.curuser)

    def getUsers(self):
        """Return a list of 'normal' users, i.e. those with a home
        directory in /home and a login shell (ending with 'sh').
        """
        return [u[0]
                for u in pwd.getpwall()
                if (u[5].startswith('/home/') and u[6].endswith('sh'))]

    def getGroups(self):
        """Return a list of 'normal' groups, i.e. those with ... ?
        """
        # This is where I would sort the groups since you're building your list
        # Lists are always ordered, so we're going to order by name.
        return sorted([g[0] for g in grp.getgrall()])

    def getUserGroups(self, user):
        """Return the list of supplemental groups for the given user.
        """
        # Same thing here.
        return sorted([gu[0] for gu in grp.getgrall() if user in gu[3]])

    def getUserInfo(self, user):
        """Return (uid, gid) for the given user.
        """
        return pwd.getpwnam(user)[2:4]


class Help(gtk.Frame):
    def __init__(self):
        gtk.Frame.__init__(self)
        self.set_border_width(5)
        sw = gtk.ScrolledWindow()
        sw.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.view = gtk.TextView()
        self.view.set_editable(False)
        # view.set_wrap_mode(gtk.WRAP_WORD)
        sw.add(self.view)
        self.add(sw)
        self.view.show()

        self.reportbuf = self.view.get_buffer()
        self.reportbuf.set_text(helptext)


class About(gtk.Frame):
    def __init__(self):
        gtk.Frame.__init__(self)
        self.set_border_width(5)
        box = gtk.VBox()
        box.set_border_width(10)
        label = gtk.Label()
        label.set_line_wrap(True)
        # label.set_alignment(0.0, 0.5)
        label.set_markup(
            abouttext +
            '\nCopyright (c) 2008   Michael Towers\nCopyright (c) 2016' +
            '   <a href=\"http://www.linuxliteos.com/development.html\">' +
            'Linux Lite</a>')

        box.pack_start(label)
        self.add(box)


class Configure(gtk.Frame):
    def __init__(self):
        gtk.Frame.__init__(self)
        self.set_border_width(10)
        label = gtk.Label()
        label.set_line_wrap(True)
        label.set_markup('<b>Not Yet implemented</b>')
        self.add(label)


class Users(gtk.HBox):
    def __init__(self):
        gtk.HBox.__init__(self, spacing=20)
        self.set_border_width(10)

        leftbox = gtk.VBox(spacing=5)

        self.grouplist = CheckList()

        self.pack_start(leftbox)
        self.pack_end(self.grouplist)

        # leftbox:
        #    user select combobox
        self.usel = SelectUser()
        leftbox.pack_start(self.usel, False)

        #    add user button -> user name + password popup
        newuser = gtk.Button("New user")
        newuser.connect('clicked', self.newUser)
        leftbox.pack_start(newuser, False)

        #    change password button -> password popup
        newpw = gtk.Button("Change password")
        newpw.connect('clicked', self.newPass)
        leftbox.pack_start(newpw, False)

        #    remove user button -> are you sure confirmation
        self.delete = gtk.Button("Remove this user")
        self.delete.connect('clicked', self.removeUser)
        leftbox.pack_start(self.delete, False)

        aqbox = gtk.HBox()
        leftbox.pack_end(aqbox, False)

        quit = gtk.Button(stock=gtk.STOCK_QUIT)
        quit.connect('clicked', gui.exit)
        aqbox.pack_start(quit)

        self.apply = gtk.Button(stock=gtk.STOCK_APPLY)
        self.apply.connect('clicked', gui.apply)
        aqbox.pack_end(self.apply)

    def enableApply(self, on):
        self.apply.set_sensitive(on)

    def setUsers(self, user=None):
        if not user:
            user = runninguser
        self.usel.setUsers(user)

    def setUser(self, user):
        self.usel.select(user)

    def displayUser(self, user):
        """If the selected user is 'root', editing of the groups and
        deleting the user should be disabled.
        If the user is the running user, deleting the user should be
        disabled.
        """
        root = (user == 'root')
        self.grouplist.setEnabled(not root)
        self.delete.set_sensitive((not root) and (user != runninguser))

    def setGroups(self, user):
        """Set up the group display widget for the given user.
        """
        self.grouplist.setGroups(user)

    def resetUser(self, user):
        self.usel.select(user)

    def newUser(self, widget, data=None):
        user, pw = popupNewUser()
        if user:
            if (pw == ''):
                # Passwordless login
                pwcrypt = ''
            else:
                # Normal MD5 password
                pwcrypt = encryptPW(pw)
            ccode, op = gui.rootrun(
                "useradd --shell=/bin/bash -m -G users,adm,cdrom,dip,plugdev,lpadmin,sambashare -p '%s' %s"
                % (pwcrypt, user))
            if (ccode != 0):
                error("It was not possible to add  user '%s'."
                      " Here is the system message:\n\n %s") % (user, op)
            else:
                self.usel.setUsers(user)

    def newPass(self, widget, data=None):
        pw = popupNewPassword()
        if (pw == ''):
            # Passwordless login
            pwcrypt = ''
        elif (pw is not None):
            # Normal MD5 password
            pwcrypt = encryptPW(pw)
        else:
            # 'Cancelled'
            return
        ccode, op = gui.rootrun("usermod -p '%s' %s" % (pwcrypt, gui.curuser))
        if (ccode != 0):
            error("The password for user '%s' could not be changed."
                  " Here is the system message:\n\n %s") % (gui.curuser, op)

    def removeUser(self, widget, data=None):
        if confirm(("Do you really want to remove user '%s', including"
                    " the home directory, i.e. losing all the data contained"
                    " therein?") % gui.curuser):

            ccode, op = gui.rootrun('userdel -r %s' % gui.curuser)
            if (ccode != 0):
                error("User '%s' could not be removed. Here is the system"
                      " message:\n\n %s") % (gui.curuser, op)

            else:
                self.usel.setUsers(runninguser)


class SelectUser(gtk.Frame):
    def __init__(self):
        gtk.Frame.__init__(self, "Select user")
        self.combo = gtk.ComboBox()

        # Need some space around the combo box. The only way I've found
        # of doing this (so far) is to add an extra layout widget ...
        border = gtk.Table(rows=2, columns=2, homogeneous=True)
        border.attach(self.combo, 0, 2, 0, 1, xpadding=3, ypadding=3)

        # Add a label to display the uid
        self.uid = gtk.Label()
        border.attach(self.uid, 1, 2, 1, 2, xpadding=3, ypadding=3)
        self.add(border)

        self.list = gtk.ListStore(str)
        self.combo.set_model(self.list)
        cell = gtk.CellRendererText()
        self.combo.pack_start(cell)
        self.combo.add_attribute(cell, 'text', 0)
        self.blocked = False
        self.combo.connect('changed', self.changed_cb)

    def setUsers(self, user):
        self.blocked = True
        self.list.clear()
        for u in (gui.getUsers() + ['root']):
            self.list.append([u])
        while gtk.events_pending():
            gtk.main_iteration(False)
        self.blocked = False
        self.select(user)

    def changed_cb(self, widget, data=None):
        if self.blocked:
            return
        i = self.combo.get_active()
        u = self.list[i][0]
        self.uid.set_text("User ID: %5d" % pwd.getpwnam(u)[2])
        gui.changeUser(u)

    def select(self, user):
        """Programmatically set the currently selected user.
        """
        i = 0
        for u in self.list:
            if (u[0] == user):
                self.combo.set_active(i)
                break
            i += 1


class CheckList(gtk.ScrolledWindow):
    def __init__(self, columnwidth=180):
        gtk.ScrolledWindow.__init__(self)
        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        self.set_shadow_type(gtk.SHADOW_IN)
        self.set_size_request(columnwidth, -1)

        self.treeview = gtk.TreeView()
        self.liststore = gtk.ListStore(str, bool, bool, str)
        self.treeview.set_model(self.liststore)
        # create CellRenderers to render the data
        celltoggle = gtk.CellRendererToggle()
        # celltoggle.set_property('activatable', True)
        celltoggle.connect('toggled', self.toggled_cb)
        celltext = gtk.CellRendererText()
        # create the TreeViewColumn to display the groups
        self.tvcolumn = gtk.TreeViewColumn("Groups")
        self.tvcolumn.set_sort_column_id(1)
        self.tvcolumn.pack_start(celltoggle, expand=False)
        self.tvcolumn.add_attribute(celltoggle, 'active', 1)
        self.tvcolumn.add_attribute(celltoggle, 'activatable', 2)
        self.tvcolumn.pack_start(celltext, expand=True)
        self.tvcolumn.add_attribute(celltext, 'text', 0)
        # add column to treeview
        self.treeview.append_column(self.tvcolumn)
        # create and add gid column
        cellnum = gtk.CellRendererText()
        cellnum.set_property('xalign', 1.0)
        gidcol = gtk.TreeViewColumn('Group ID', cellnum, text=3)
        self.treeview.append_column(gidcol)
        gidcol.set_sort_column_id(2)
        # place treeview in scrolled window
        self.add(self.treeview)

    def toggled_cb(self, widget, path, data=None):
        self.liststore[path][1] = not self.liststore[path][1]
        gui.enableApply(self.groupsChanged() is not None)

    def setEnabled(self, enable):
        self.treeview.set_sensitive(enable)

    def setGroups(self, user):
        """Write the list of groups to the list, and set toggles
        according to the membership of the current user.
        """
        groups = gui.getGroups()
        usergroups = gui.getUserGroups(user)
        uid, gid = gui.getUserInfo(user)
        self.gidnm = grp.getgrgid(gid)[0]
        self.liststore.clear()
        for g in groups:
            gn = grp.getgrnam(g)[2]
            if (g == self.gidnm):
                self.liststore.append([g, True, False, gn])
            else:
                enable = (user != 'root') and (
                    g not in ('root', 'bin', 'daemon', 'sys', 'adm'))
                self.liststore.append([g, g in usergroups, enable, gn])

    def groupsChanged(self):
        """If the displayed group memberships differ from those set in
        the system, return the list of displayed group memberships,
        otherwise <None>.
        """
        # Get the list of groups for the present user according to
        # the checklist.
        nglist = []
        for r in self.liststore:
            if (r[1] and (r[0] != self.gidnm)):
                nglist.append(r[0])
        if (gui.getUserGroups(gui.curuser) != nglist):
            return nglist
        else:
            return None


def popupRootPassword():
    dialog = gtk.Dialog(
        parent=gui,
        flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
        buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OK,
                 gtk.RESPONSE_ACCEPT))
    dialog.set_property('title', 'Enter Password')
    label = gtk.Label()
    label.set_markup("To complete this operation you must enter"
                     " the <b>Administrator</b> password:")
    label.set_line_wrap(True)
    label.set_alignment(0.0, 0.5)
    dialog.vbox.pack_start(label)
    label.show()
    entry = gtk.Entry(max=20)
    entry.set_visibility(False)
    dialog.vbox.pack_start(entry)
    entry.show()
    entry.connect('activate', enterKey_cb, dialog)
    if (dialog.run() == gtk.RESPONSE_ACCEPT):
        val = entry.get_text()
    else:
        val = None
    dialog.destroy()
    return val


def enterKey_cb(widget, dialog):
    """A callback for the Enter key in dialogs.
    """
    dialog.response(gtk.RESPONSE_ACCEPT)


def popupNewPassword():
    """Dialog for entering a new password, which may be empty. Returns
    <None> if cancelled.
    """
    dialog = gtk.Dialog(
        parent=gui,
        flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
        buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OK,
                 gtk.RESPONSE_ACCEPT))
    dialog.set_title("Linux Lite User Manager")
    label = gtk.Label("Enter new password:")
    label.set_alignment(0.0, 0.5)
    dialog.vbox.pack_start(label)
    label.show()
    entry = gtk.Entry(max=20)
    entry.set_visibility(False)
    dialog.vbox.pack_start(entry)
    entry.show()
    label2 = gtk.Label("Reenter new password:")
    label2.set_alignment(0.0, 0.5)
    dialog.vbox.pack_start(label2)
    label2.show()
    entry2 = gtk.Entry(max=20)
    entry2.set_visibility(False)
    dialog.vbox.pack_start(entry2)
    entry2.show()
    val = None
    while (dialog.run() == gtk.RESPONSE_ACCEPT):
        v = entry.get_text()
        if (v == entry2.get_text()):
            val = v
            break
        error("The passwords do not match.")
    dialog.destroy()
    return val


def popupNewUser():
    """Dialog for entering a new user, complete with password, which may
    be empty. Returns a pair (user, password), or (<None>, <None>) if
    cancelled.
    """
    dialog = gtk.Dialog(
        parent=gui,
        flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
        buttons=(gtk.STOCK_CANCEL, gtk.RESPONSE_REJECT, gtk.STOCK_OK,
                 gtk.RESPONSE_ACCEPT))
    dialog.set_property('title', 'New User')
    labelu = gtk.Label("Enter user ('login') name:")
    labelu.set_alignment(0.0, 0.5)
    dialog.vbox.pack_start(labelu)
    labelu.show()
    entryu = gtk.Entry(max=20)
    dialog.vbox.pack_start(entryu)
    entryu.show()
    label = gtk.Label("Enter new password:")
    label.set_alignment(0.0, 0.5)
    dialog.vbox.pack_start(label)
    label.show()
    entry = gtk.Entry(max=20)
    entry.set_visibility(False)
    dialog.vbox.pack_start(entry)
    entry.show()
    label2 = gtk.Label("Reenter new password:")
    label2.set_alignment(0.0, 0.5)
    dialog.vbox.pack_start(label2)
    label2.show()
    entry2 = gtk.Entry(max=20)
    entry2.set_visibility(False)
    dialog.vbox.pack_start(entry2)
    entry2.show()
    pw = None
    user = None
    while (dialog.run() == gtk.RESPONSE_ACCEPT):
        v = entry.get_text()
        if (v == entry2.get_text()):
            pw = v
            user = entryu.get_text()
            break
        error("The passwords do not match.")
    dialog.destroy()
    return (user, pw)


def encryptPW(pw):
    salt = '$1$'
    for i in range(8):
        salt += random.choice("./0123456789abcdefghijklmnopqrstuvwxyz"
                              "ABCDEFGHIJKLMNOPQRSTUVWXYZ")
    return crypt.crypt(pw, salt)


def error(message):
    md = gtk.MessageDialog(
        parent=gui,
        flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
        type=gtk.MESSAGE_ERROR,
        buttons=gtk.BUTTONS_CLOSE,
        message_format=message)
    md.run()
    md.destroy()


def confirm(message):
    md = gtk.MessageDialog(
        parent=gui,
        flags=gtk.DIALOG_MODAL | gtk.DIALOG_DESTROY_WITH_PARENT,
        type=gtk.MESSAGE_QUESTION,
        buttons=gtk.BUTTONS_YES_NO,
        message_format=message)
    val = md.run()
    md.destroy()
    return (val == gtk.RESPONSE_YES)


def asroot(cmd, pw):
    """Run a command as root, using the given password.
    """
    child = pexpect.spawn('su-to-root -c "%s"' % cmd)
    child.expect(':')
    child.sendline(pw)
    child.expect(pexpect.EOF)
    o = child.before.strip()
    return (0 if (o == '') else 1, o)


if __name__ == "__main__":
    gui = Luser()
    gui.init()
    # Start with the current effective user
    runninguser = pwd.getpwuid(os.getuid())[0]
    gui.setUsers()
    gui.mainLoop()
