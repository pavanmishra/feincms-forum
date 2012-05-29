from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.db.transaction import commit_on_success
from feincmsforum.models import Category, Forum, Topic, Post, Profile
import datetime
import logging

from .export_models.kunena import KunenaCategory, KunenaPost, KunenaUser, KunenaPostText
from .import_util import BaseImporter, prepareImport
import re

class Command(BaseCommand):
    """
    First import the Kunena DB backup:
    mysql -u <dbuser> -p <dbname> --default-character-set=utf8 < <backupfile>
    NOTE: do not forget to add router to settings:
    settings.DATABASE_ROUTERS = ['feincmsforum.routers.KunenaRouter']
    """
    help = u'Imports kunena forum sql dump'

    def handle(self, *args, **options):
        logging.basicConfig(level = logging.INFO)
        prepareImport()
        UserImporter().doImport()
        CategoryImporter().doImport()
        ForumImporter().doImport()
        PostImporter().doImport()

# ------------------------ importers ------------------------------------------

class KunenaImporter(BaseImporter):
    def _get_parent(self, cat):
        if cat.parent == 0:
            return None
        else:
            return KunenaCategory.objects.get(pk=cat.parent)

    def _find_root(self, cat):
        curr = self._get_parent(cat)
        while curr.parent != 0:
            curr = self._get_parent(curr)
        return curr

    def _get_user(self, email, name):
        if User.objects.filter(email__exact=email).exists():
            return User.objects.get(email=email)
        if User.objects.filter(username__iexact=name).exists():
            return User.objects.filter(username__iexact=name)[0]
        logging.warn('User %s with email %s not found' %(name, email))
        return None


class UserImporter(KunenaImporter):
    def get_queryset(self):
        return KunenaUser.objects.all()\
                    .exclude(username__icontains='[bot]')\
                    .exclude(username__icontains='[Google]')\
                    .exclude(username__icontains='[crawler]')\
                    .exclude(username__icontains='[spider]')\
                    .exclude(username__exact='Anonymous')

    @commit_on_success
    def processObject(self, o):
        try:
            u = User.objects.get(email__iexact=o.email)
        except User.DoesNotExist:
            nameparts = unicode(o.name).split(' ')
            if len(nameparts) == 1:
                first_name, last_name = nameparts[0], ''
            else:
                first_name, last_name = nameparts[0], ' '.join(nameparts[1:])
            u = User(username=unicode(o.username), first_name=first_name,
                 last_name=last_name, email=o.email)
            u.save()
        if not Profile.objects.filter(user__exact=u).exists():
            Profile(user=u).save()


class CategoryImporter(KunenaImporter):
    def get_queryset(self):
        return KunenaCategory.objects.filter(parent__exact=0)

    @commit_on_success
    def processObject(self, o):
        if not Category.objects.filter(name__icontains=o.name).exists():
            Category(name=unicode(o.name)).save()


class ForumImporter(KunenaImporter):
    def get_queryset(self):
        return KunenaCategory.objects.all().exclude(parent__exact=0)

    @commit_on_success
    def processObject(self, o):
        if not Forum.objects.filter(name__icontains=o.name).exists():
            parent = KunenaCategory.objects.get(pk=o.parent)
            try:
                category = Category.objects.get(name=parent.name)
            except Category.DoesNotExist:
                root = self._find_root(o)
                category = Category.objects.get(name=root.name)

            Forum(category=category, description=unicode(o.description),
                  name=unicode(o.name)).save()


class PostImporter(KunenaImporter):
    _smileRegexps = {r'<img class="cometchat_smiley" height="[0-9]{1,}" width="[0-9]{1,}" src="[^\"]" alt=":-\)">' : ':)' }

    def get_queryset(self):
        return KunenaPost.objects.all()

    @commit_on_success
    def processObject(self, o):
        text = KunenaPostText.objects.get(pk=o.id)
        topic = self._solveTopic(o)
        if not Post.objects.filter(body__iexact=text.message).exists():
            author = self._get_user(o.email, o.name)
            created = datetime.datetime.fromtimestamp(o.time)
            bodyText = self._process_text(unicode(text.message))

            Post(topic=topic, body=bodyText, user_ip=o.ip,
                 user=author, created=created).save()

    def _solveTopic(self, o):
        topic = KunenaPost.objects.filter(thread=o.thread).order_by('time')[0]
        try:
            return Topic.objects.get(name=topic.subject)
        except Topic.DoesNotExist:
            kunenacat = KunenaCategory.objects.get(pk=o.catid)
            forum = Forum.objects.get(name=kunenacat.name)
            author = self._get_user(topic.email, topic.name)

            createdtime = datetime.datetime.fromtimestamp(topic.time)
            topic = Topic(forum=forum, views=topic.hits, created=createdtime,
                  name=unicode(topic.subject), user=author)
            topic.save()
            return topic

    def _process_text(self, text):
        for r, repl in self._smileRegexps.items():
            text = re.sub(r, repl, text)
        return text
