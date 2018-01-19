# -*- coding: utf-8 -*-
import logging

import re
import sqlalchemy
from flask import flash
from flask import url_for
from flask_babel import gettext

from mycodo.databases.models import DisplayOrder
from mycodo.databases.models import Dashboard
from mycodo.mycodo_flask.extensions import db
from mycodo.mycodo_flask.utils.utils_general import add_display_order
from mycodo.mycodo_flask.utils.utils_general import delete_entry_with_id
from mycodo.mycodo_flask.utils.utils_general import flash_form_errors
from mycodo.mycodo_flask.utils.utils_general import flash_success_errors
from mycodo.mycodo_flask.utils.utils_general import reorder
from mycodo.utils.system_pi import csv_to_list_of_int
from mycodo.utils.system_pi import list_to_csv

logger = logging.getLogger(__name__)


#
# Dashboard
#

def dashboard_add(form_base, form_object, display_order):
    """
    Add an item to the dashboard

    Either Graph, Gauge, or Camera
    """
    action = '{action} {controller}'.format(
        action=gettext("Add"),
        controller=gettext("Dashboard"))
    error = []

    new_graph = Dashboard()
    new_graph.graph_type = form_base.dashboard_type.data
    new_graph.name = form_base.name.data

    # Graph
    if (form_base.dashboard_type.data == 'graph' and
            (form_base.name.data and
             form_object.width.data and
             form_object.height.data and
             form_object.xaxis_duration.data and
             form_object.refresh_duration.data)):

        error = graph_error_check(form_object, error)

        if form_object.math_ids.data:
            math_ids_joined = ";".join(form_object.math_ids.data)
            new_graph.math_ids = math_ids_joined
        if form_object.pid_ids.data:
            pid_ids_joined = ";".join(form_object.pid_ids.data)
            new_graph.pid_ids = pid_ids_joined
        if form_object.relay_ids.data:
            relay_ids_joined = ";".join(form_object.relay_ids.data)
            new_graph.relay_ids = relay_ids_joined
        if form_object.sensor_ids.data:
            sensor_ids_joined = ";".join(form_object.sensor_ids.data)
            new_graph.sensor_ids_measurements = sensor_ids_joined
        new_graph.width = form_object.width.data
        new_graph.height = form_object.height.data
        new_graph.x_axis_duration = form_object.xaxis_duration.data
        new_graph.refresh_duration = form_object.refresh_duration.data
        new_graph.enable_auto_refresh = form_object.enable_auto_refresh.data
        new_graph.enable_xaxis_reset = form_object.enable_xaxis_reset.data
        new_graph.enable_title = form_object.enable_title.data
        new_graph.enable_navbar = form_object.enable_navbar.data
        new_graph.enable_rangeselect = form_object.enable_range.data
        new_graph.enable_export = form_object.enable_export.data
        new_graph.enable_manual_y_axis = form_object.enable_manual_y_axis.data
        new_graph.y_axis_min = form_object.y_axis_min.data
        new_graph.y_axis_max = form_object.y_axis_max.data

        try:
            if not error:
                new_graph.save()
                flash(gettext(
                    "Graph with ID %(id)s successfully added",
                    id=new_graph.id),
                    "success")

                DisplayOrder.query.first().graph = add_display_order(
                    display_order, new_graph.id)
                db.session.commit()
        except sqlalchemy.exc.OperationalError as except_msg:
            error.append(except_msg)
        except sqlalchemy.exc.IntegrityError as except_msg:
            error.append(except_msg)

    # Gauge
    elif (form_base.dashboard_type.data in ['gauge_angular', 'gauge_solid'] and
          form_object.sensor_ids.data):

        error = gauge_error_check(form_object, error)

        if form_base.dashboard_type.data == 'gauge_solid':
            new_graph.range_colors = '0.2,#33CCFF;0.4,#55BF3B;0.6,#DDDF0D;0.8,#DF5353'
        elif form_base.dashboard_type.data == 'gauge_angular':
            new_graph.range_colors = '0,25,#33CCFF;25,50,#55BF3B;50,75,#DDDF0D;75,100,#DF5353'
        new_graph.width = form_object.width.data
        new_graph.height = form_object.height.data
        new_graph.max_measure_age = form_object.max_measure_age.data
        new_graph.refresh_duration = form_object.refresh_duration.data
        new_graph.y_axis_min = form_object.y_axis_min.data
        new_graph.y_axis_max = form_object.y_axis_max.data
        new_graph.sensor_ids_measurements = form_object.sensor_ids.data[0]
        try:
            if not error:
                new_graph.save()
                flash(gettext(
                    "Gauge with ID %(id)s successfully added",
                    id=new_graph.id),
                    "success")

                DisplayOrder.query.first().graph = add_display_order(
                    display_order, new_graph.id)
                db.session.commit()
        except sqlalchemy.exc.OperationalError as except_msg:
            error.append(except_msg)
        except sqlalchemy.exc.IntegrityError as except_msg:
            error.append(except_msg)

    # Camera
    elif (form_base.dashboard_type.data == 'camera' and
          form_object.camera_id.data):

        new_graph.width = form_object.width.data
        new_graph.height = form_object.height.data
        new_graph.refresh_duration = form_object.refresh_duration.data
        new_graph.camera_max_age = form_object.camera_max_age.data
        new_graph.camera_id = form_object.camera_id.data
        new_graph.camera_image_type = form_object.camera_image_type.data
        try:
            if not error:
                new_graph.save()
                flash(gettext(
                    "Camera with ID %(id)s successfully added",
                    id=new_graph.id),
                    "success")

                DisplayOrder.query.first().graph = add_display_order(
                    display_order, new_graph.id)
                db.session.commit()
        except sqlalchemy.exc.OperationalError as except_msg:
            error.append(except_msg)
        except sqlalchemy.exc.IntegrityError as except_msg:
            error.append(except_msg)

    else:
        flash_form_errors(form_base)
        return

    flash_success_errors(error, action, url_for('routes_page.page_dashboard'))


def dashboard_mod(form_base, form_object, request_form):
    """Modify the settings of an item on the dashboard"""
    action = '{action} {controller}'.format(
        action=gettext("Modify"),
        controller=gettext("Dashboard"))
    error = []

    def is_rgb_color(color_hex):
        return bool(re.compile(r'#[a-fA-F0-9]{6}$').match(color_hex))

    error = graph_error_check(form_object, error)

    mod_graph = Dashboard.query.filter(
        Dashboard.id == form_base.dashboard_id.data).first()
    mod_graph.name = form_base.name.data

    # Graph Mod
    if form_base.dashboard_type.data == 'graph':

        error = graph_error_check(form_object, error)

        # Get variable number of color inputs, turn into CSV string
        colors = {}
        short_list = []
        f = request_form
        for key in f.keys():
            if 'color_number' in key:
                for value in f.getlist(key):
                    if not is_rgb_color(value):
                        error.append("Invalid hex color value")
                    colors[key[12:]] = value
        sorted_list = [(k, colors[k]) for k in sorted(colors)]
        for each_color in sorted_list:
            short_list.append(each_color[1])
        sorted_colors_string = ",".join(short_list)
        mod_graph.custom_colors = sorted_colors_string

        mod_graph.use_custom_colors = form_object.use_custom_colors.data

        if form_object.math_ids.data:
            math_ids_joined = ";".join(form_object.math_ids.data)
            mod_graph.math_ids = math_ids_joined
        else:
            mod_graph.math_ids = ''

        if form_object.pid_ids.data:
            pid_ids_joined = ";".join(form_object.pid_ids.data)
            mod_graph.pid_ids = pid_ids_joined
        else:
            mod_graph.pid_ids = ''

        if form_object.relay_ids.data:
            relay_ids_joined = ";".join(form_object.relay_ids.data)
            mod_graph.relay_ids = relay_ids_joined
        else:
            mod_graph.relay_ids = ''

        if form_object.sensor_ids.data:
            sensor_ids_joined = ";".join(form_object.sensor_ids.data)
            mod_graph.sensor_ids_measurements = sensor_ids_joined
        else:
            mod_graph.sensor_ids_measurements = ''

        mod_graph.width = form_object.width.data
        mod_graph.height = form_object.height.data
        mod_graph.x_axis_duration = form_object.xaxis_duration.data
        mod_graph.refresh_duration = form_object.refresh_duration.data
        mod_graph.enable_auto_refresh = form_object.enable_auto_refresh.data
        mod_graph.enable_xaxis_reset = form_object.enable_xaxis_reset.data
        mod_graph.enable_title = form_object.enable_title.data
        mod_graph.enable_navbar = form_object.enable_navbar.data
        mod_graph.enable_export = form_object.enable_export.data
        mod_graph.enable_rangeselect = form_object.enable_range.data
        mod_graph.enable_manual_y_axis = form_object.enable_manual_y_axis.data
        mod_graph.y_axis_min = form_object.y_axis_min.data
        mod_graph.y_axis_max = form_object.y_axis_max.data

    # If a gauge type is changed, the color format must change
    elif (form_base.dashboard_type.data in ['gauge_angular', 'gauge_solid'] and
            mod_graph.graph_type != form_base.dashboard_type.data):

        mod_graph.graph_type = form_base.dashboard_type.data
        if form_base.dashboard_type.data == 'gauge_solid':
            mod_graph.range_colors = '0.2,#33CCFF;0.4,#55BF3B;0.6,#DDDF0D;0.8,#DF5353'
        elif form_base.dashboard_type.data == 'gauge_angular':
            mod_graph.range_colors = '0,25,#33CCFF;25,50,#55BF3B;50,75,#DDDF0D;75,100,#DF5353'

    # Gauge Mod
    elif form_base.dashboard_type.data in ['gauge_angular', 'gauge_solid']:

        error = gauge_error_check(form_object, error)

        colors_hex = {}
        f = request_form
        sorted_colors_string = ""

        if form_base.dashboard_type.data == 'gauge_angular':
            # Combine all color form inputs to dictionary
            for key in f.keys():
                if ('color_hex_number' in key or
                        'color_low_number' in key or
                        'color_high_number' in key):
                    if int(key[17:]) not in colors_hex:
                        colors_hex[int(key[17:])] = {}
                if 'color_hex_number' in key:
                    for value in f.getlist(key):
                        if not is_rgb_color(value):
                            error.append("Invalid hex color value")
                        colors_hex[int(key[17:])]['hex'] = value
                elif 'color_low_number' in key:
                    for value in f.getlist(key):
                        colors_hex[int(key[17:])]['low'] = value
                elif 'color_high_number' in key:
                    for value in f.getlist(key):
                        colors_hex[int(key[17:])]['high'] = value

        elif form_base.dashboard_type.data == 'gauge_solid':
            # Combine all color form inputs to dictionary
            for key in f.keys():
                if ('color_hex_number' in key or
                        'color_stop_number' in key):
                    if int(key[17:]) not in colors_hex:
                        colors_hex[int(key[17:])] = {}
                if 'color_hex_number' in key:
                    for value in f.getlist(key):
                        if not is_rgb_color(value):
                            error.append("Invalid hex color value")
                        colors_hex[int(key[17:])]['hex'] = value
                elif 'color_stop_number' in key:
                    for value in f.getlist(key):
                        colors_hex[int(key[17:])]['stop'] = value

        # Build string of colors and associated gauge values
        for i, _ in enumerate(colors_hex):
            try:
                if form_base.dashboard_type.data == 'gauge_angular':
                    sorted_colors_string += "{},{},{}".format(
                        colors_hex[i]['low'],
                        colors_hex[i]['high'],
                        colors_hex[i]['hex'])
                elif form_base.dashboard_type.data == 'gauge_solid':
                    try:
                        if 0 > colors_hex[i]['stop'] > 1:
                            error.append("Color stops must be between 0 and 1")
                        sorted_colors_string += "{},{}".format(
                            colors_hex[i]['stop'],
                            colors_hex[i]['hex'])
                    except Exception:
                        sorted_colors_string += "0,{}".format(
                            colors_hex[i]['hex'])
                if i < len(colors_hex) - 1:
                    sorted_colors_string += ";"
            except Exception as err_msg:
                error.append(err_msg)

        mod_graph.range_colors = sorted_colors_string
        mod_graph.width = form_object.width.data
        mod_graph.height = form_object.height.data
        mod_graph.refresh_duration = form_object.refresh_duration.data
        mod_graph.y_axis_min = form_object.y_axis_min.data
        mod_graph.y_axis_max = form_object.y_axis_max.data
        mod_graph.max_measure_age = form_object.max_measure_age.data
        if form_object.sensor_ids.data[0]:
            sensor_ids_joined = ";".join(form_object.sensor_ids.data)
            mod_graph.sensor_ids_measurements = sensor_ids_joined
        else:
            error.append("A valid Measurement must be selected")

    # Camera Mod
    elif form_base.dashboard_type.data == 'camera':
        mod_graph.width = form_object.width.data
        mod_graph.height = form_object.height.data
        mod_graph.refresh_duration = form_object.refresh_duration.data
        mod_graph.camera_max_age = form_object.camera_max_age.data
        mod_graph.camera_id = form_object.camera_id.data
        mod_graph.camera_image_type = form_object.camera_image_type.data

    else:
        flash_form_errors(form_base)

    if not error:
        try:
            db.session.commit()
        except sqlalchemy.exc.OperationalError as except_msg:
            error.append(except_msg)
        except sqlalchemy.exc.IntegrityError as except_msg:
            error.append(except_msg)

    flash_success_errors(error, action, url_for('routes_page.page_dashboard'))


def dashboard_del(form_base):
    """Delete an item on the dashboard"""
    action = '{action} {controller}'.format(
        action=gettext("Delete"),
        controller=gettext("Dashboard"))
    error = []

    try:
        delete_entry_with_id(Dashboard,
                             form_base.dashboard_id.data)
        display_order = csv_to_list_of_int(DisplayOrder.query.first().graph)
        display_order.remove(int(form_base.dashboard_id.data))
        DisplayOrder.query.first().graph = list_to_csv(display_order)
        db.session.commit()
    except Exception as except_msg:
        error.append(except_msg)
    flash_success_errors(error, action, url_for('routes_page.page_dashboard'))



def dashboard_reorder(dashboard_id, display_order, direction):
    """reorder something on the dashboard"""
    action = '{action} {controller}'.format(
        action=gettext("Reorder"),
        controller=gettext("Dashboard"))
    error = []
    try:
        status, reord_list = reorder(display_order,
                                     dashboard_id,
                                     direction)
        if status == 'success':
            DisplayOrder.query.first().graph = ','.join(map(str, reord_list))
            db.session.commit()
        else:
            error.append(reord_list)
    except Exception as except_msg:
        error.append(except_msg)
    flash_success_errors(error, action, url_for('routes_page.page_dashboard'))


def graph_error_check(form, error):
    """Determine if there are any errors in the graph form"""
    if (form.enable_manual_y_axis.data and
            (form.y_axis_min.data is None or
             form.y_axis_max.data is None)):
        error.append("If Manual Y-Axis is selected, Minimum and Maximum must be set")
    return error


def gauge_error_check(form, error):
    """Determine if there are any errors in the gauge form"""
    if not form.sensor_ids.data[0]:
        error.append("A valid Measurement must be selected")
    return error