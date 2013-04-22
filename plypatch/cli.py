"""
ply: git-based patch management
"""
import argparse
import sys

import plypatch
from plypatch import git


def die(msg):
    print msg
    sys.exit(1)


def die_on_conflicts():
    print "Patch did not apply cleanly. To fix:"
    print
    print "\t1) Fix conflicts in affected files"
    print "\n\t2) `git add` affected files"
    print "\n\t3) Run `ply resolve` to refresh the patch and"\
          " apply the rest\n\t   of the patches in the series."
    sys.exit(1)


def die_on_uncommitted_changes():
    die('ERROR: Uncommitted changes, commit or discard before continuing.')


class CLICommand(object):
    __command__ = None

    def __init__(self, working_repo):
        self.working_repo = working_repo

    def _add_subparser(self, subparsers):
        short_help = getattr(self.do, '__doc__', '')
        subparser = subparsers.add_parser(self.__command__, help=short_help)
        self.add_arguments(subparser)
        return subparser

    def add_arguments(self, subparser):
        """Override to add additional flags and arguments"""
        pass

    def do(self, args):
        """This doc-string becomes part of --help output"""
        raise NotImplementedError


class AbortCommand(CLICommand):
    __command__ = 'abort'

    def do(self, args):
        """Abort in-progress restore operation"""
        self.working_repo.abort()


class CheckCommand(CLICommand):
    __command__ = 'check'

    def do(self, args):
        """Peform a health check on the patch-repo"""
        status, errors = self.working_repo.check_patch_repo()

        print status.upper()

        if status == 'ok':
            return

        if errors['no_file']:
            print 'Entry in series-file but patch not present:'
            for patch_name in errors['no_file']:
                print '\t- %s' % patch_name

        if errors['no_series_entry']:
            print 'Patch is present but no entry in series file:'
            for patch_name in errors['no_series_entry']:
                print '\t- %s' % patch_name


class GraphCommand(CLICommand):
    __command__ = 'graph'

    def do(self, args):
        """Graph patch dependencies in DOT format"""
        print self.working_repo.patch_repo.patch_dependency_dot_graph()


class InitCommand(CLICommand):
    __command__ = 'init'

    def add_arguments(self, subparser):
        subparser.add_argument('path', action='store',
                               help='Path to patch-repo')

    def do(self, args):
        """Initialize a new patch-repo"""
        plypatch.PatchRepo(args.path).initialize()


class LinkCommand(CLICommand):
    __command__ = 'link'

    def add_arguments(self, subparser):
        subparser.add_argument('path', action='store',
                               help='Path to patch-repo')

    def do(self, args):
        """Link a working-repo to a patch-repo"""
        try:
            self.working_repo.link(args.path)
        except plypatch.exc.AlreadyLinkedToPatchRepo:
            die('Already linked to a patch-repo')


class ResolveCommand(CLICommand):
    __command__ = 'resolve'

    def do(self, args):
        """Mark conflicts for a patch as resolved and continue applying the
        rest of the patches in the series
        """
        try:
            self.working_repo.resolve()
        except plypatch.git.exc.PatchDidNotApplyCleanly:
            die_on_conflicts()


class RestoreCommand(CLICommand):
    __command__ = 'restore'

    def do(self, args):
        """Apply the patch series to the the current branch of the
        working-repo"""
        try:
            self.working_repo.restore()
        except plypatch.exc.UncommittedChanges:
            die_on_uncommitted_changes()
        except plypatch.git.exc.PatchDidNotApplyCleanly:
            die_on_conflicts()


class RollbackCommand(CLICommand):
    __command__ = 'rollback'

    def do(self, args):
        """Rollback to the last upstream commit"""
        try:
            self.working_repo.rollback()
        except plypatch.exc.NoPatchesApplied:
            die('ERROR: cannot rollback, no patches applied')
        except plypatch.exc.UncommittedChanges:
            die_on_uncommitted_changes()


class SaveCommand(CLICommand):
    __command__ = 'save'

    def add_arguments(self, subparser):
        subparser.add_argument('since', action='store')
        subparser.add_argument('--prefix', action='store')

    def do(self, args):
        """Save set of commits to patch-repo"""
        try:
            self.working_repo.save(args.since, prefix=args.prefix)
        except plypatch.exc.UncommittedChanges:
            die_on_uncommitted_changes()


class SkipCommand(CLICommand):
    __command__ = 'skip'

    def do(self, args):
        """Skips current patch and removes it from patch-repo then continues by
        applying rest of the patches in the series
        """
        try:
            self.working_repo.skip()
        except plypatch.git.exc.PatchDidNotApplyCleanly:
            die_on_conflicts()


class StatusCommand(CLICommand):
    __command__ = 'status'

    def do(self, args):
        """Show status of the working-repo"""
        status = self.working_repo.status

        if status == 'restore-in-progress':
            die('Restore in progress, use skip or resolve to continue')
        elif status == 'no-patches-applied':
            die('No patches applied')
        else:
            die('All patches applied')


class UnlinkCommand(CLICommand):
    __command__ = 'unlink'

    def do(self, args):
        """Unlink working-repo from patch-repo"""
        try:
            self.working_repo.unlink()
        except plypatch.exc.NoLinkedPatchRepo:
            die('Not linked to a patch-repo')


COMMANDS = [AbortCommand, CheckCommand, GraphCommand, InitCommand,
            LinkCommand, ResolveCommand, RestoreCommand, RollbackCommand,
            SaveCommand, SkipCommand, StatusCommand, UnlinkCommand]


def main():
    parser = argparse.ArgumentParser(prog='ply', description=__doc__)
    parser.add_argument('-v', '--verbose', action='store_true', default=False,
                        help="show verbose output")
    parser.add_argument('--version', action='version',
                        version='%(prog)s ' + plypatch.__version__)

    subparsers = parser.add_subparsers(help='Sub-commands')

    working_repo = plypatch.WorkingRepo('.')

    for cmd_class in COMMANDS:
        cmd = cmd_class(working_repo)
        subparser = cmd._add_subparser(subparsers)
        subparser.set_defaults(func=cmd.do)

    args = parser.parse_args()

    working_repo.quiet = not args.verbose

    # Dispatch to command handler (`do`)
    args.func(args)