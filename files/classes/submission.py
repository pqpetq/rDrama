from os import environ
import random
import re
import time
from urllib.parse import urlparse
from flask import render_template
from sqlalchemy import *
from sqlalchemy.orm import relationship, deferred
from files.__main__ import Base
from files.helpers.const import *
from files.helpers.lazy import lazy
from .flags import Flag
from .comment import Comment
from flask import g
from .sub import *
from .votes import CommentVote

class Submission(Base):
	__tablename__ = "submissions"

	id = Column(Integer, primary_key=True)
	author_id = Column(Integer, ForeignKey("users.id"))
	edited_utc = Column(Integer, default=0)
	created_utc = Column(Integer)
	thumburl = Column(String)
	is_banned = Column(Boolean, default=False)
	bannedfor = Column(Boolean)
	ghost = Column(Boolean, default=False)
	views = Column(Integer, default=0)
	deleted_utc = Column(Integer, default=0)
	distinguish_level = Column(Integer, default=0)
	stickied = Column(String)
	stickied_utc = Column(Integer)
	sub = Column(String, ForeignKey("subs.name"))
	is_pinned = Column(Boolean, default=False)
	private = Column(Boolean, default=False)
	club = Column(Boolean, default=False)
	comment_count = Column(Integer, default=0)
	is_approved = Column(Integer, ForeignKey("users.id"))
	over_18 = Column(Boolean, default=False)
	is_bot = Column(Boolean, default=False)
	upvotes = Column(Integer, default=1)
	downvotes = Column(Integer, default=0)
	realupvotes = Column(Integer, default=1)
	app_id=Column(Integer, ForeignKey("oauth_apps.id"))
	title = Column(String)
	title_html = Column(String)
	url = Column(String)
	body = Column(String)
	body_html = Column(String)
	flair = Column(String)
	ban_reason = Column(String)
	embed_url = Column(String)
	new = Column(Boolean)

	author = relationship("User", primaryjoin="Submission.author_id==User.id")
	oauth_app = relationship("OauthApp", viewonly=True)
	approved_by = relationship("User", uselist=False, primaryjoin="Submission.is_approved==User.id", viewonly=True)
	awards = relationship("AwardRelationship", viewonly=True)
	reports = relationship("Flag", viewonly=True)
	comments = relationship("Comment", primaryjoin="Comment.parent_submission==Submission.id")
	subr = relationship("Sub", primaryjoin="foreign(Submission.sub)==remote(Sub.name)", viewonly=True)

	bump_utc = deferred(Column(Integer, server_default=FetchedValue()))

	def __init__(self, *args, **kwargs):
		if "created_utc" not in kwargs: kwargs["created_utc"] = int(time.time())
		super().__init__(*args, **kwargs)

	def __repr__(self):
		return f"<Submission(id={self.id})>"

	@property
	@lazy
	def controversial(self):
		if self.downvotes > 5 and 0.25 < self.upvotes / self.downvotes < 4: return True
		return False

	@lazy
	def flags(self, v):
		flags = g.db.query(Flag).filter_by(post_id=self.id).order_by(Flag.created_utc).all()
		if not (v and (v.shadowbanned or v.admin_level > 2)):
			for flag in flags:
				if flag.user.shadowbanned:
					flags.remove(flag)
		return flags
	
	@property
	@lazy
	def options(self):
		return g.db.query(Comment).filter_by(parent_submission = self.id, author_id = AUTOPOLLER_ID, level=1).order_by(Comment.id)


	@property
	@lazy
	def choices(self):
		return g.db.query(Comment).filter_by(parent_submission = self.id, author_id = AUTOCHOICE_ID, level=1).order_by(Comment.id)


	@property
	@lazy
	def bet_options(self):
		return g.db.query(Comment).filter_by(parent_submission = self.id, author_id = AUTOBETTER_ID, level=1)

	def total_poll_voted(self, v):
		if v:
			for option in self.options:
				if option.poll_voted(v): return True
		return False

	def total_choice_voted(self, v):
		if v and self.choices:
			return g.db.query(CommentVote).filter(CommentVote.user_id == v.id, CommentVote.comment_id.in_([x.id for x in self.choices])).all()
		return False

	def total_bet_voted(self, v):
		if "closed" in self.body.lower(): return True
		if v:
			for option in self.bet_options:
				if option.poll_voted(v): return True
		return False

	@property
	@lazy
	def created_datetime(self):
		return str(time.strftime("%d/%B/%Y %H:%M:%S UTC", time.gmtime(self.created_utc)))

	@property
	@lazy
	def created_datetime(self):
		return str(time.strftime("%d/%B/%Y %H:%M:%S UTC", time.gmtime(self.created_utc)))

	@property
	@lazy
	def age_string(self):

		age = int(time.time()) - self.created_utc

		if age < 60:
			return "just now"
		elif age < 3600:
			minutes = int(age / 60)
			return f"{minutes}m ago"
		elif age < 86400:
			hours = int(age / 3600)
			return f"{hours}hr ago"
		elif age < 2678400:
			days = int(age / 86400)
			return f"{days}d ago"

		now = time.gmtime()
		ctd = time.gmtime(self.created_utc)

		months = now.tm_mon - ctd.tm_mon + 12 * (now.tm_year - ctd.tm_year)
		if now.tm_mday < ctd.tm_mday:
			months -= 1

		if months < 12:
			return f"{months}mo ago"
		else:
			years = int(months / 12)
			return f"{years}yr ago"

	@property
	@lazy
	def edited_string(self):

		if not self.edited_utc: return "never"

		age = int(time.time()) - self.edited_utc

		if age < 60:
			return "just now"
		elif age < 3600:
			minutes = int(age / 60)
			return f"{minutes}m ago"
		elif age < 86400:
			hours = int(age / 3600)
			return f"{hours}hr ago"
		elif age < 2678400:
			days = int(age / 86400)
			return f"{days}d ago"

		now = time.gmtime()
		ctd = time.gmtime(self.edited_utc)
		months = now.tm_mon - ctd.tm_mon + 12 * (now.tm_year - ctd.tm_year)

		if months < 12:
			return f"{months}mo ago"
		else:
			years = now.tm_year - ctd.tm_year
			return f"{years}yr ago"


	@property
	@lazy
	def edited_datetime(self):
		return str(time.strftime("%d/%B/%Y %H:%M:%S UTC", time.gmtime(self.edited_utc)))


	@property
	@lazy
	def score(self):
		return self.upvotes - self.downvotes

	@property
	@lazy
	def fullname(self):
		return f"t2_{self.id}"	


	@property
	@lazy
	def shortlink(self):
		link = f"/post/{self.id}"
		if self.sub: link = f"/h/{self.sub}{link}"

		if self.club: return link + '/-'

		output = title_regex.sub('', self.title.lower())
		output = output.split()[:6]
		output = '-'.join(output)

		if not output: output = '-'

		return f"{link}/{output}"

	@property
	@lazy
	def permalink(self):
		return SITE_FULL + self.shortlink

	@property
	@lazy
	def domain(self):
		if not self.url: return None
		if self.url.startswith('/'): return SITE
		domain = urlparse(self.url).netloc
		if domain.startswith("www."): domain = domain.split("www.")[1]
		return domain.replace("old.reddit.com", "reddit.com")

	@property
	@lazy
	def author_name(self):
		if self.ghost: return '👻'
		else: return self.author.username

	@property
	@lazy
	def is_youtube(self):
		return self.domain == "youtube.com" and self.embed_url and self.embed_url.startswith('<lite-youtube') 

	@property
	@lazy
	def thumb_url(self):
		if self.over_18: return "/assets/images/nsfw.webp?v=1"
		elif not self.url: return f"/assets/images/{SITE_NAME}/default_text.webp?v=1"
		elif self.thumburl: 
			if self.thumburl.startswith('/'): return SITE_FULL + self.thumburl
			return self.thumburl
		elif self.is_youtube or self.is_video: return "/assets/images/default_thumb_yt.webp?v=1"
		else: return "/assets/images/default_thumb_link.webp?v=1"

	@property
	@lazy
	def json_raw(self):
		flags = {}
		for f in self.flags(None): flags[f.user.username] = f.reason

		data = {'author_name': self.author_name if self.author else '',
				'permalink': self.permalink,
				'shortlink': self.shortlink,
				'is_banned': bool(self.is_banned),
				'deleted_utc': self.deleted_utc,
				'created_utc': self.created_utc,
				'id': self.id,
				'title': self.title,
				'is_nsfw': self.over_18,
				'is_bot': self.is_bot,
				'thumb_url': self.thumb_url,
				'domain': self.domain,
				'url': self.realurl(None),
				'body': self.body,
				'body_html': self.body_html,
				'created_utc': self.created_utc,
				'edited_utc': self.edited_utc or 0,
				'comment_count': self.comment_count,
				'score': self.score,
				'upvotes': self.upvotes,
				'downvotes': self.downvotes,
				'stickied': self.stickied,
				'private' : self.private,
				'distinguish_level': self.distinguish_level,
				'voted': self.voted if hasattr(self, 'voted') else 0,
				'flags': flags,
				'club': self.club,
				}

		if self.ban_reason:
			data["ban_reason"]=self.ban_reason

		return data

	@property
	@lazy
	def json_core(self):

		if self.is_banned:
			return {'is_banned': True,
					'deleted_utc': self.deleted_utc,
					'ban_reason': self.ban_reason,
					'id': self.id,
					'title': self.title,
					'permalink': self.permalink,
					}
		elif self.deleted_utc:
			return {'is_banned': bool(self.is_banned),
					'deleted_utc': True,
					'id': self.id,
					'title': self.title,
					'permalink': self.permalink,
					}

		return self.json_raw

	@property
	@lazy
	def json(self):

		data=self.json_core
		
		if self.deleted_utc or self.is_banned:
			return data

		data["author"]='👻' if self.ghost else self.author.json_core
		data["comment_count"]=self.comment_count

	
		if "replies" in self.__dict__:
			data["replies"]=[x.json_core for x in self.replies]

		if "voted" in self.__dict__:
			data["voted"] = self.voted

		return data

	def award_count(self, kind):
		return len([x for x in self.awards if x.kind == kind])

	@lazy
	def realurl(self, v):
		if v and self.url and self.url.startswith("https://old.reddit.com/"):

			url = self.url.replace("old.reddit.com", v.reddit)

			if '/comments/' in url and "sort=" not in url:
				if "?" in url: url += "&context=9" 
				else: url += "?context=8"
				if v.controversial: url += "&sort=controversial"
			return url
		elif self.url:
			if v and v.nitter and '/i/' not in self.url and '/retweets' not in self.url: return self.url.replace("www.twitter.com", "nitter.net").replace("twitter.com", "nitter.net")
			if self.url.startswith('/'): return SITE_FULL + self.url
			return self.url
		else: return ""
 
	def realbody(self, v):
		if self.club and not (v and (v.paid_dues or v.id == self.author_id)): return f"<p>{CC} ONLY</p>"

		body = self.body_html or ""

		body = censor_slurs(body, v)

		if v:
			body = body.replace("old.reddit.com", v.reddit)

			if v.nitter and '/i/' not in body and '/retweets' not in body: body = body.replace("www.twitter.com", "nitter.net").replace("twitter.com", "nitter.net")

		if v and v.shadowbanned and v.id == self.author_id and 86400 > time.time() - self.created_utc > 20:
			ti = max(int((time.time() - self.created_utc)/60), 1)
			maxupvotes = min(ti, 11)
			rand = random.randint(0, maxupvotes)
			if self.upvotes < rand:
				amount = random.randint(0, 3)
				if amount == 1:
					self.views += amount*random.randint(3, 5)
					self.upvotes += amount
					g.db.add(self)
					g.db.commit()

		for c in self.options:
			body += f'<div class="custom-control"><input type="checkbox" class="custom-control-input" id="{c.id}" name="option"'
			if c.poll_voted(v): body += " checked"
			if v: body += f''' onchange="poll_vote('{c.id}', '{self.id}')"'''
			else: body += f''' onchange="poll_vote_no_v('{c.id}', '{self.id}')"'''
			body += f'''><label class="custom-control-label" for="{c.id}">{c.body_html}<span class="presult-{self.id}'''
			if not self.total_poll_voted(v): body += ' d-none'	
			body += f'"> - <a href="/votes?link=t3_{c.id}"><span id="poll-{c.id}">{c.upvotes}</span> votes</a></span></label></div>'

		curr = self.total_choice_voted(v)
		if curr: curr = " value=" + str(curr[0].comment_id)
		else: curr = ''
		body += f'<input class="d-none" id="current-{self.id}"{curr}>'

		for c in self.choices:
			body += f'''<div class="custom-control"><input name="choice-{self.id}" autocomplete="off" class="custom-control-input" type="radio" id="{c.id}" onchange="choice_vote('{c.id}','{self.id}')"'''
			if c.poll_voted(v): body += " checked "
			body += f'''><label class="custom-control-label" for="{c.id}">{c.body_html}<span class="presult-{self.id}'''
			if not self.total_choice_voted(v): body += ' d-none'	
			body += f'"> - <a href="/votes?link=t3_{c.id}"><span id="choice-{c.id}">{c.upvotes}</span> votes</a></span></label></div>'

		for c in self.bet_options:
			body += f'''<div class="custom-control mt-3"><input autocomplete="off" class="custom-control-input bet" type="radio" id="{c.id}" onchange="bet_vote('{c.id}')"'''
			if c.poll_voted(v): body += " checked "
			if not (v and v.coins > 200) or self.total_bet_voted(v): body += " disabled "
			body += f'''><label class="custom-control-label" for="{c.id}">{c.body_html} - <a href="/votes?link=t3_{c.id}"><span id="bet-{c.id}">{c.upvotes}</span> bets</a>'''
			if not self.total_bet_voted(v):
				body += '''<span class="cost"> (cost of entry: 200 coins)</span>'''
			body += "</label>"
			if v and v.admin_level > 2:
				body += f'''<button class="btn btn-primary px-2 mx-2" style="font-size:10px;padding:2px;margin-top:-5px" onclick="post_toast(this,'/distribute/{c.id}')">Declare winner</button>'''
			body += "</div>"


		if self.author.sig_html and (self.author_id == MOOSE_ID or (not self.ghost and not (v and v.sigs_disabled))):
			body += f"<hr>{self.author.sig_html}"

		return body

	def plainbody(self, v):
		if self.club and not (v and (v.paid_dues or v.id == self.author_id)): return f"<p>{CC} ONLY</p>"

		body = self.body

		if not body: return ""

		body = censor_slurs(body, v)

		if v:
			body = body.replace("old.reddit.com", v.reddit)

			if v.nitter and '/i/' not in body and '/retweets' not in body: body = body.replace("www.twitter.com", "nitter.net").replace("twitter.com", "nitter.net")

		return body

	def print(self):
		print(f'post: {self.id}, author: {self.author_id}', flush=True)
		return ''

	@lazy
	def realtitle(self, v):
		if self.club and not (v and (v.paid_dues or v.id == self.author_id)):
			if v: return random.choice(TROLLTITLES).format(username=v.username)
			elif SITE == 'cringetopia.org': return f'Please make an account to see this post'
			else: return f'{CC} MEMBERS ONLY'
		elif self.title_html: title = self.title_html
		else: title = self.title

		title = censor_slurs(title, v)

		return title

	@lazy
	def plaintitle(self, v):
		if self.club and not (v and (v.paid_dues or v.id == self.author_id)):
			if v: return random.choice(TROLLTITLES).format(username=v.username)
			else: return f'{CC} MEMBERS ONLY'
		else: title = self.title

		title = censor_slurs(title, v)

		return title

	@property
	@lazy
	def is_video(self):
		return self.url and any((self.url.lower().endswith(x) for x in ('.mp4','.webm','.mov'))) and embed_fullmatch_regex.fullmatch(self.url)

	@property
	@lazy
	def is_image(self):
		if self.url and (self.url.lower().endswith('.webp') or self.url.lower().endswith('.jpg') or self.url.lower().endswith('.png') or self.url.lower().endswith('.gif') or self.url.lower().endswith('.jpeg') or self.url.lower().endswith('?maxwidth=9999') or self.url.lower().endswith('&fidelity=high')) and (self.url.startswith('/') or self.url.startswith(f'{SITE_FULL}/') or embed_fullmatch_regex.fullmatch(self.url)):
			return True
		return False

	@lazy
	def active_flags(self, v): return len(self.flags(v))