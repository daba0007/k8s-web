# -*- coding: utf-8 -*-
# Generated by Django 1.11.8 on 2017-12-14 06:24
from __future__ import unicode_literals

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('form', '0001_initial'),
    ]

    operations = [
        migrations.AlterField(
            model_name='code_data',
            name='code',
            field=models.IntegerField(primary_key=True, serialize=False, verbose_name='工号'),
        ),
        migrations.AlterField(
            model_name='user_data',
            name='money',
            field=models.IntegerField(verbose_name='工资'),
        ),
    ]
