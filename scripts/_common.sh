#!/bin/bash

app="arcenal_report"

configure_files() {
    ynh_config_add_nginx
    ynh_config_add_systemd
}

set_runtime_permissions() {
    chown "$app:www-data" "$install_dir"
    chown -R "$app:www-data" "$install_dir/web"
    chown -R "$app:$app" "$install_dir/backend" "$data_dir"
    find "$install_dir/web" -type d -exec chmod 750 {} +
    find "$install_dir/web" -type f -exec chmod 640 {} +
    find "$install_dir/backend" -type d -exec chmod 750 {} +
    find "$install_dir/backend" -type f -exec chmod 640 {} +
    chmod 750 "$install_dir" "$data_dir" "$data_dir/uploads"
}
