messages:
	python manage.py makemessages -l vi
	python manage.py makemessages -l en

compile:
	python manage.py compilemessages

translations: messages compile