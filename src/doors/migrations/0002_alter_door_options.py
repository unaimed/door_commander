# Generated by Django 3.2.7 on 2021-09-27 21:31

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('doors', '0001_initial'),
    ]

    operations = [
        migrations.AlterModelOptions(
            name='door',
            options={'permissions': [('open_door', 'Can open any door'), ('assume_correct_location', 'Can open doors from anywhere')]},
        ),
    ]
