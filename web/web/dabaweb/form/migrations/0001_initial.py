# -*- coding: utf-8 -*-
# Generated by Django 1.11.8 on 2017-12-14 06:23
from __future__ import unicode_literals

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    initial = True

    dependencies = [
    ]

    operations = [
        migrations.CreateModel(
            name='Code_data',
            fields=[
                ('code', models.IntegerField(max_length=30, primary_key=True, serialize=False, verbose_name='名字')),
                ('group', models.CharField(max_length=100, verbose_name='组名')),
            ],
            options={
                'verbose_name': '号码管理',
                'verbose_name_plural': '号码管理',
            },
        ),
        migrations.CreateModel(
            name='User',
            fields=[
                ('uid', models.IntegerField(primary_key=True, serialize=False, verbose_name='id')),
                ('code_link', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='form.Code_data')),
            ],
            options={
                'verbose_name': '主键管理',
                'verbose_name_plural': '主键管理',
            },
        ),
        migrations.CreateModel(
            name='User_data',
            fields=[
                ('name', models.CharField(max_length=30, primary_key=True, serialize=False, verbose_name='名字')),
                ('money', models.IntegerField(max_length=100, verbose_name='钱')),
            ],
            options={
                'verbose_name': '用户管理',
                'verbose_name_plural': '用户管理',
            },
        ),
        migrations.AddField(
            model_name='user',
            name='name_link',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='form.User_data'),
        ),
    ]
