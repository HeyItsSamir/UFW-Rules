#
# backend_iptables.py: iptables backend for ufw
#
# Copyright (C) 2008 Canonical Ltd.
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License version 3,
#    as published by the Free Software Foundation.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import os
import re
import sys
from tempfile import mkstemp

from ufw.common import UFWError, UFWRule, config_dir, state_dir
from ufw.util import warn, debug, cmd, cmd_pipe
import ufw.backend


class UFWBackendIptables(ufw.backend.UFWBackend):
    def __init__(self, d):
        self.comment_str = "# " + ufw.common.programName + "_comment #"

        files = {}
        files['rules'] = os.path.join(state_dir, 'user.rules')
        files['before_rules'] = os.path.join(config_dir, 'ufw/before.rules')
        files['after_rules'] = os.path.join(config_dir, 'ufw/after.rules')
        files['rules6'] = os.path.join(state_dir, 'user6.rules')
        files['before6_rules'] = os.path.join(config_dir, 'ufw/before6.rules')
        files['after6_rules'] = os.path.join(config_dir, 'ufw/after6.rules')
        files['init'] = os.path.join(config_dir, 'init.d/ufw')

        ufw.backend.UFWBackend.__init__(self, "iptables", d, files)

    def get_loglevel(self):
        '''Gets current log level of firewall'''
        level = 1
        rstr = _("Logging: on")
        for f in [self.files['rules'], self.files['rules6'], \
                  self.files['before_rules'], self.files['before6_rules'], \
                  self.files['after_rules'], self.files['after6_rules']]:
            orig = ufw.util.open_file_read(f)
            for line in orig:
                # If find one occurence of the comment_str, we know the user
                # ran "logging off"
                if self.comment_str in line:
                    rstr = _("Logging: off")
                    level = 0
                    orig.close()
                    break

            orig.close()

        return (level, rstr)

    def get_default_policy(self):
        '''Get current policy'''
        rstr = _("Default:") 
        if self.defaults['default_input_policy'] == "accept":
            rstr += " allow"
        else:
            rstr += " deny"

        return rstr

    def set_default_policy(self, policy):
        '''Sets default policy of firewall'''
        if not self.dryrun:
            if policy == "allow":
                self.set_default(self.files['defaults'], \
                                            "DEFAULT_INPUT_POLICY", \
                                            "\"ACCEPT\"")
            elif policy == "deny":
                self.set_default(self.files['defaults'], \
                                            "DEFAULT_INPUT_POLICY", \
                                            "\"DROP\"")
            else:
                err_msg = _("Unsupported policy '%s'") % (policy)
                raise UFWError(err_msg)

        rstr = _("Default policy changed to '%s'\n") % (policy)
        rstr += _("(be sure to update your rules accordingly)")

        return rstr

    def set_loglevel(self, level):
        '''Sets log level of firewall'''
        for f in [self.files['rules'], self.files['rules6'], \
                  self.files['before_rules'], self.files['before6_rules'], \
                  self.files['after_rules'], self.files['after6_rules']]:
            try:
                fns = ufw.util.open_files(f)
            except Exception:
                raise
            fd = fns['tmp']

            pat = re.compile(r'^-.*\sLOG\s')
            if level == "on":
                pat = re.compile(r'^#.*\sLOG\s')

            if not self.dryrun:
                for line in fns['orig']:
                    if pat.search(line):
                        if level == "off":
                            os.write(fd, self.comment_str + ' ' + line)
                        else:
                            pat_comment = re.compile(r"^" + \
                                                     self.comment_str + "\s*")
                            os.write(fd, pat_comment.sub('', line))
                    else:
                        os.write(fd, line)

            if self.dryrun:
                ufw.util.close_files(fns, False)
            else:
                ufw.util.close_files(fns)
    
        if level == "off":
            return _("Logging disabled")
        else:
            return _("Logging enabled")

    def get_status(self):
        '''Show current status of firewall'''
        out = ""
        out6 = ""
        if self.dryrun:
            out = "> " + _("Checking iptables\n")
            if self.use_ipv6():
                out += "> " + _("Checking ip6tables\n")
            return out

        # Is the firewall loaded at all?
        (rc, out) = cmd(['iptables', '-L', 'ufw-user-input', '-n'])
        if rc != 0:
            return _("Status: not loaded")

        err_msg = _("problem running")

        # Get the output of iptables for parsing
        (rc, out) = cmd(['iptables', '-L', '-n'])
        if rc != 0:
            raise UFWError(err_msg + " iptables")

        if self.use_ipv6():
            (rc, out6) = cmd(['ip6tables', '-L', 'ufw6-user-input', '-n'])
            if rc != 0:
                raise UFWError(err_msg + " ip6tables")
            if out6 == "":
                return out6

        if out == "" and out6 == "":
            return _("Status: loaded")

        str = ""
        rules = []
        pat_chain = re.compile(r'^Chain ')
        pat_target = re.compile(r'^target')
        for type in ["v4", "v6"]:
            pat_ufw = re.compile(r'^Chain ufw-user-input')
            if type == "v6":
                pat_ufw = re.compile(r'^Chain ufw6-user-input')
            lines = out
            if type == "v6":
                lines = out6
            in_ufw_input = False
            for line in lines.split('\n'):
                if pat_ufw.search(line):
                    in_ufw_input = True
                    continue
                elif pat_chain.search(line):
                    in_ufw_input = False
                    continue
                elif pat_target.search(line):
                    pass
                elif in_ufw_input:
                    r = self._parse_iptables_status(line, type)
                    if r is not None:
                        rules.append(r)

        for r in rules:
            location = {}
            for loc in [ 'dst', 'src' ]:
                location[loc] = ""

                port = r.dport
                tmp = r.dst
                if loc == 'src':
                    port = r.sport
                    tmp = r.src
                
                if tmp != "0.0.0.0/0" and tmp != "::/0":
                    location[loc] = tmp
                
                if port != "any":
                    if location[loc] == "":
                        location[loc] = port
                    else:
                        location[loc] += " " + port

                    if r.protocol != "any":
                        location[loc] += ":" + r.protocol

                if port == "any":
                    if tmp == "0.0.0.0/0":
                        location[loc] = "Anywhere"
                    if tmp == "::/0":
                        location[loc] = "Anywhere (v6)"

            str += "%-26s %-8s%s\n" % (location['dst'], r.action.upper(), \
                    location['src'])

        if str != "":
            header = "\n\n%-26s %-8s%s\n" % (_("To"), _("Action"), _("From"))
            header += "%-26s %-8s%s\n" % (_("--"), _("------"), _("----"))
            str = header + str 

        (level, logging_str) = self.get_loglevel()
        policy_str = self.get_default_policy()
        return _("Status: loaded\n%s\n%s%s") % (logging_str, policy_str, str)

    def stop_firewall(self):
        '''Stops the firewall'''
        openconf = '''*filter
:INPUT ACCEPT [0:0]
:FORWARD ACCEPT [0:0]
:OUTPUT ACCEPT [0:0]
COMMIT
'''
        if self.dryrun:
            print "> iptables -F"
            print "> iptables -X"
            print "> echo\n" + openconf + "> | iptables-restore"
            if self.use_ipv6():
                print "> ip6tables -F"
                print "> ip6tables -X"
                print "> echo\n" + openconf + "> | ip6tables-restore"
            return

        try:
            (tmp, tmpname) = mkstemp()
        except Exception:
            raise
        os.write(tmp, openconf)
        os.close(tmp)

        err_msg = _("problem running")

        # Flush the firewall
        (rc, out) = cmd(['iptables', '-F'])
        if rc != 0:
            raise UFWError(err_msg + " iptables 'flush'")

        # Remove user chains
        (rc, out) = cmd(['iptables', '-X'])
        if rc != 0:
            raise UFWError(err_msg + " iptables 'delete'")

        # Set default open
        (rc, out) = cmd_pipe(['cat', tmpname], ['iptables-restore'])
        if rc != 0:
            raise UFWError(err_msg + " iptables")

        if self.use_ipv6():
            # Flush the firewall
            (rc, out) = cmd(['ip6tables', '-F'])
            if rc != 0:
                raise UFWError(err_msg + " ip6tables 'flush'")

            # Remove user chains
            (rc, out) = cmd(['ip6tables', '-X'])
            if rc != 0:
                raise UFWError(err_msg + " ip6tables 'delete'")

            # Set default open
            (rc, out) = cmd_pipe(['cat', tmpname], ['ip6tables-restore'])
            if rc != 0:
                raise UFWError(err_msg + " ip6tables")

        os.unlink(tmpname)

    def start_firewall(self):
        '''Starts the firewall'''
        err_msg = _("problem running")
        if self.dryrun:
            print "> " + _("running initscript")
        else:
            (rc, out) = cmd([self.files['init'], 'start'])
            if rc != 0:
                raise UFWError(err_msg + " init script")

        # When ipv6 not enabled, just enable it on loopback
        if not self.use_ipv6() and os.path.exists("/proc/sys/net/ipv6"):
            ipv6conf = '''*filter
:INPUT DROP [0:0]
:FORWARD DROP [0:0]
:OUTPUT DROP [0:0]

-A INPUT -i lo -j ACCEPT
-A OUTPUT -o lo -j ACCEPT

COMMIT
'''
            if not self.dryrun:
                (rc, out) = cmd_pipe(['echo', ipv6conf], ['ip6tables-restore'])
                if rc != 0:
                    # Don't error here, as the user may have disabled ipv6
                    # and doesn't have ipv6 support
                    warn(err_msg + " ip6tables")

    def _need_reload(self, v6):
        '''Check if loaded rules are consistent with written rules'''
        if self.dryrun:
            return False

        prefix = "ufw"
        exe = "iptables"
        if v6:
            prefix = "ufw6"
            exe = "ip6tables"

        for chain in [ 'input', 'output', 'forward', 'limit' ]:
            if v6 and chain == "limit":
                continue

            (rc, out) = cmd([exe, '-n', '-L', prefix + "-user-" + chain])
            if rc != 0:
                return True
            
        return False

    def _reload_user_rules(self):
        '''Reload firewall rules file'''
        err_msg = _("problem running")
        if self.dryrun:
            print "> iptables-restore < " + self.files['rules'] 
            if self.use_ipv6():
                print "> ip6tables-restore < " + self.files['rules6'] 
        else:
            (rc, out) = cmd_pipe(['cat', self.files['rules']], \
                                 ['iptables-restore', '-n'])
            if rc != 0:
                raise UFWError(err_msg + " iptables")

            if self.use_ipv6():
                (rc, out) = cmd_pipe(['cat', self.files['rules6']], \
                                     ['ip6tables-restore', '-n'])
                if rc != 0:
                    raise UFWError(err_msg + " ip6tables")

    def _get_rules_from_formatted(self, frule):
        '''Return list of iptables rules appropriate for sending'''
        snippets = []

        pat_proto = re.compile(r'-p all ')
        pat_port = re.compile(r'port ')
        if pat_proto.search(frule):
            if pat_port.search(frule):
                snippets.append(pat_proto.sub('-p tcp ', frule))
                snippets.append(pat_proto.sub('-p udp ', frule))
            else:
                snippets.append(pat_proto.sub('', frule))
        else:
            snippets.append(frule)

        pat_limit = re.compile(r' -j LIMIT')
        for i, s in enumerate(snippets):
            if pat_limit.search(s):
                tmp1 = pat_limit.sub(' -m state --state NEW -m recent --set', s)
                tmp2 = pat_limit.sub(' -m state --state NEW -m recent --update --seconds 30 --hitcount 6 -j ufw-user-limit', s)
                snippets[i] = tmp2
                snippets.insert(i, tmp1)

        return snippets

    def _parse_iptables_status(self, line, type):
        '''Parses a line from iptables -L -n'''
        fields = line.split()

        if type == "v6":
            # ip6tables hack since its opt field is blank (unlike iptables)
            fields.insert(2, '--')

        if len(fields) < 5:
            dbg_msg = _("Couldn't parse line '%s'") % (line)
            debug(dbg_msg)
            return None

        rule = UFWRule("ACCEPT", "any", "any")
        if fields[0] == 'ACCEPT':
            rule.set_action('allow')
        elif fields[0] == 'DROP':
            rule.set_action('deny')
        elif fields[0] == "ufw-user-limit":
            rule.set_action('limit')
        else:
            # RETURN and LOG are valid, but we skip them
            return None

        if fields[1] == 'tcp' or fields[1] == 'udp':
            rule.set_protocol(fields[1])
        elif fields[1] == "0" or fields[1] == "all":
            rule.set_protocol('any')
        else:
            rule.set_protocol('UNKNOWN')

        if type == "v6":
            # ip6tables hack since it doesn't have a space between the 
            # destination address and the protocol on a large destination
            # address (see Debian bug #464244).
            mashed = fields[4][(len(fields[4]) - 3):]
            if mashed == 'tcp' or mashed == 'udp':
                fields.insert(5, mashed)
                fields[4] = fields[4][:(len(fields[4]) - 3)]

        try:
            rule.set_src(fields[3])
            rule.set_dst(fields[4])
        except:
            warn_msg = _("Couldn't parse line '%s'") % (line)
            warn(warn_msg)
            return None

        if len(fields) >= 7:
            if re.match('dpt', fields[6]):
                rule.set_port(fields[6][4:], "dst")
            elif re.match('spt', fields[6]):
                rule.set_port(fields[6][4:], "src")
        
        if len(fields) >= 8:
            if re.match('dpt', fields[7]):
                rule.set_port(fields[7][4:], "dst")
            elif re.match('spt', fields[7]):
                rule.set_port(fields[7][4:], "src")

        if type == "v6":
            rule.set_v6(True)
        else:
            rule.set_v6(False)
        
        return rule
        
    def _read_rules(self):
        '''Read in rules that were added by ufw.'''
        rfns = [self.files['rules']]
        if self.use_ipv6():
            rfns.append(self.files['rules6'])

        for f in rfns:
            orig = ufw.util.open_file_read(f)

            pat_tuple = re.compile(r'^### tuple ###\s*')
            for line in orig:
                if pat_tuple.match(line):
                    tuple = pat_tuple.sub('', line)
                    tmp = re.split(r'\s+', tuple.strip())
                    if len(tmp) != 6:
                        warn_msg = _("Skipping malformed tuple (bad length): %s") % (tuple)
                        warn(warn_msg)
                    else:
                        try:
                            rule = UFWRule(tmp[0], tmp[1], tmp[2], tmp[3],
                                           tmp[4], tmp[5])
                            if f == self.files['rules6']:
                                rule.set_v6(True)
                                self.rules6.append(rule)
                            else:
                                rule.set_v6(False)
                                self.rules.append(rule)
                        except UFWError:
                            warn_msg = _("Skipping malformed tuple: %s") % \
                                        (tuple)
                            warn(warn_msg)

            orig.close()

    def _write_rules(self, v6=False):
        '''Write out new rules to file to user chain file'''
        rules_file = self.files['rules']
        if v6:
            rules_file = self.files['rules6']

        try:
            fns = ufw.util.open_files(rules_file)
        except Exception:
            raise

        chain_prefix = "ufw"
        rules = self.rules
        if v6:
            chain_prefix = "ufw6"
            rules = self.rules6

        if self.dryrun:
            fd = sys.stdout.fileno()
        else:
            fd = fns['tmp']

        # Write header
        os.write(fd, "*filter\n")
        os.write(fd, ":" + chain_prefix + "-user-input - [0:0]\n")
        os.write(fd, ":" + chain_prefix + "-user-output - [0:0]\n")
        os.write(fd, ":" + chain_prefix + "-user-forward - [0:0]\n")

        if chain_prefix == "ufw":
            # Rate limiting only supported with IPv4
            os.write(fd, ":" + chain_prefix + "-user-limit - [0:0]\n")

        os.write(fd, "### RULES ###\n")

        # Write rules
        for r in rules:
            rule_str = "-A " + chain_prefix + "-user-input " + \
                       r.format_rule() + "\n"
            os.write(fd, "\n### tuple ###" + " %s %s %s %s %s %s\n" % \
                     (r.action, r.protocol, r.dport, r.dst, r.sport, r.src))
            for s in self._get_rules_from_formatted(rule_str):
                os.write(fd, s)

        # Write footer
        os.write(fd, "\n### END RULES ###\n")
        os.write(fd, "-A " + chain_prefix + "-user-input -j RETURN\n")
        os.write(fd, "-A " + chain_prefix + "-user-output -j RETURN\n")
        os.write(fd, "-A " + chain_prefix + "-user-forward -j RETURN\n")

        if chain_prefix == "ufw":
            # Rate limiting only supported with IPv4
            os.write(fd, "-A " + chain_prefix + "-user-limit -m limit " + \
                         "--limit 3/minute -j LOG --log-prefix " + \
                         "\"[UFW LIMIT]: \"\n")
            os.write(fd, "-A " + chain_prefix + "-user-limit -j DROP\n")

        os.write(fd, "COMMIT\n")

        if self.dryrun:
            ufw.util.close_files(fns, False)
        else:
            ufw.util.close_files(fns)

    def set_rule(self, rule):
        '''Updates firewall with rule by:
        * appending the rule to the chain if new rule and firewall enabled
        * deleting the rule from the chain if found and firewall enabled
        * updating user rules file
        * reloading the user rules file if rule is modified
        '''
        if rule.v6:
            if not self.use_ipv6():
                err_msg = _("Adding IPv6 rule failed: IPv6 not enabled")
                raise UFWError(err_msg)
            if rule.action == 'limit':
                # Netfilter doesn't have ip6t_recent yet, so skip
                return _("Skipping unsupported IPv6 '%s' rule") % (rule.action)

        newrules = []
        found = False
        modified = False
        delete = False

        rules = self.rules
        if rule.v6:
            rules = self.rules6

        # First construct the new rules list
        for r in rules:
            ret = UFWRule.match(r, rule)
            if ret == 0 and not found:
                # If find the rule, add it if it's not to be removed, otherwise
                # skip it.
                found = True
                if not rule.remove:
                    newrules.append(rule)
            elif ret < 0 and not rule.remove:
                # If only the action is different, replace the rule if it's not
                # to be removed.
                found = True
                modified = True
                newrules.append(rule)
            else:
                newrules.append(r)

        # Add rule to the end if it was not already added.
        if not found and not rule.remove:
            newrules.append(rule)

        if rule.v6:
            self.rules6 = newrules
        else:
            self.rules = newrules

        # Update the user rules file
        try:
            self._write_rules(rule.v6)
        except:
            err_msg = _("Couldn't update rules file")
            UFWError(err_msg)

        rstr = _("Rules updated")
        if rule.v6:
            rstr = _("Rules updated (v6)")

        # Operate on the chains
        if self._is_enabled():
            flag = ""
            if modified or self._need_reload(rule.v6):
                # Reload the chain
                try:
                    self._reload_user_rules()
                except:
                    raise
                rstr = _("Rule updated")
            elif found and rule.remove:
                flag = '-D'
                rstr = _("Rule deleted")
            elif not found and not modified and not rule.remove:
                flag = '-A'
                rstr = _("Rule added")

            if flag != "":
                exe = "iptables"
                chain = "ufw-user-input"
                if rule.v6:
                    exe = "ip6tables"
                    chain = "ufw6-user-input"
                    rstr += " (v6)"

                # Is the firewall running?
                err_msg = _("Could not update running firewall")
                (rc, out) = cmd([exe, '-L', chain, '-n'])
                if rc != 0:
                    raise UFWError(err_msg)

                for s in self._get_rules_from_formatted(rule.format_rule()):
                    (rc, out) = cmd([exe, flag, chain] + s.split())
                    if rc != 0:
                        print >> sys.stderr, out
                        UFWError(err_msg)

                    # delete the RETURN rule then add it back, so it is at the
                    # end
                    if flag == "-A":
                        (rc, out) = cmd([exe, '-D', chain, '-j', 'RETURN'])
                        if rc != 0:
                            print >> sys.stderr, out

                        (rc, out) = cmd([exe, '-A', chain, '-j', 'RETURN'])
                        if rc != 0:
                            print >> sys.stderr, out
        return rstr


