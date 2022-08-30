from django.db import models

class Version(models.Model):
    key = models.CharField(max_length=50, default="", primary_key=True)
    oldver = models.CharField(max_length=50, default="")
    newver = models.CharField(max_length=50, default="")
    timestamp = models.DateTimeField(auto_now=True)

class Status(models.Model):
    key = models.CharField(max_length=50, default="", primary_key=True)
    status = models.CharField(max_length=30, default="")
    detail = models.CharField(max_length=200, default="")
    workflow = models.CharField(max_length=20, default="")
    timestamp = models.DateTimeField(auto_now=True)

class Package(models.Model):
    id = models.AutoField(primary_key=True)
    key = models.CharField(max_length=50, default="")
    package = models.CharField(max_length=100, default="")
    age = models.PositiveSmallIntegerField(default=0)
    timestamp = models.DateTimeField(auto_now_add=True)
