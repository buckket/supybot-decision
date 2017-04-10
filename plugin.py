###
# Copyright (c) 2017, buckket
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   * Redistributions of source code must retain the above copyright notice,
#     this list of conditions, and the following disclaimer.
#   * Redistributions in binary form must reproduce the above copyright notice,
#     this list of conditions, and the following disclaimer in the
#     documentation and/or other materials provided with the distribution.
#   * Neither the name of the author of this software nor the name of
#     contributors to this software may be used to endorse or promote products
#     derived from this software without specific prior written consent.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
# AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
# LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
# CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
# SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
# INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
# CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
# ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

###

import supybot.utils as utils
from supybot.commands import *
import supybot.plugins as plugins
import supybot.ircutils as ircutils
import supybot.ircmsgs as ircmsgs
import supybot.callbacks as callbacks
import supybot.log as log
try:
    from supybot.i18n import PluginInternationalization
    _ = PluginInternationalization('Decision')
except ImportError:
    # Placeholder that allows to run the plugin on a bot
    # without the i18n module
    _ = lambda x: x

from sedeprot import *

# TODO: Specify valid values before first round (optional)
# TODO: Implement a timeout, dropout condition


class SedeprotBridge:
    def __init__(self, irc, users):
        self.irc = irc
        self.dp = DecisionProcess(participants=users)

    @staticmethod
    def escape_values(values):
        return ['"{}"'.format(value) for value in values]

    def reply(self, target, message):
        self.irc.queueMsg(ircmsgs.privmsg(target, message))

    def start_process(self):
        for user in self.dp.participants.keys():
            self.reply(user, 'Hello this is supybot-decision, please answer with your preference.')
            self.reply(user, 'Other users in this decision finding process: {}'.format(
                ', '.join(self.dp.participants.keys())))

    def add_vote(self, user, value):
        try:
            self.dp.add_vote(user, value)
        except ValueError:
            self.reply(user, 'Please choose a valid value, "{}" is not allowed.'.format(value))
            return False
        except AlreadyVotedError:
            self.reply(user, 'You already voted in this round, please wait for others to finish.'.format(value))
            return False
        except DuplicateError:
            self.reply(user, 'You already voted for "{}", please choose something else.'.format(value))
            return False

        old_round = self.dp.round
        new_round, score, conclusion = self.dp.check_consent()
        self.reply(user, 'You voted for "{}" in round {}.'.format(value, old_round))
        if score and conclusion:
            for ruser in self.dp.participants.keys():
                self.reply(ruser, 'Final result after {} rounds: {}. Score: {}'.format(
                    new_round, ', '.join(self.escape_values(conclusion)), score))
                for ouser, ovoted in self.dp.get_votes().iteritems():
                    self.reply(ruser, '{} voted: {}'.format(ouser, ', '.join(self.escape_values(ovoted))))
            return True
        elif old_round != new_round:
            for ruser in self.dp.participants.keys():
                self.reply(ruser, 'No conclusion in round {}, starting new round. Please choose a new value.'.format(
                    old_round))
                for ouser, ovoted in self.dp.get_votes().iteritems():
                    self.reply(ruser, '{} voted so far: {}'.format(
                        ouser, ', '.join(self.escape_values(ovoted))))
            return False
        else:
            self.reply(user, 'Waiting for other users to choose their value.')
            return False


class Decision(callbacks.Plugin):
    """A self-enforcing protocol for collaborative decision-making"""

    def __init__(self, irc):
        self.__parent = super(Decision, self)
        self.__parent.__init__(irc)

        self.running_decision = None

    def decision(self, irc, msg, args, others):
        """Start a new decision process"""
        users = [msg.nick] + others
        if not self.running_decision:
            self.running_decision = SedeprotBridge(irc, users)
            self.running_decision.start_process()
        else:
            irc.reply('A decision process is already running.')
            return

    def doPrivmsg(self, irc, msg):
        if ircmsgs.isCtcp(msg) and not ircmsgs.isAction(msg):
            return
        if msg.args[0] == irc.nick and self.running_decision and msg.nick in self.running_decision.dp.participants.keys():
            log.debug("Message:" + msg.args[1])
            if self.running_decision.add_vote(msg.nick, msg.args[1]):
                self.running_decision = None

    decision = wrap(decision, [many('nick')])

Class = Decision


# vim:set shiftwidth=4 softtabstop=4 expandtab textwidth=79:
