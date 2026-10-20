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
    chown -R "$app:$app" "$install_dir/bin"
    find "$install_dir/web" -type d -exec chmod 750 {} +
    find "$install_dir/web" -type f -exec chmod 640 {} +
    find "$install_dir/backend" -type d -exec chmod 750 {} +
    find "$install_dir/backend" -type f -exec chmod 640 {} +
    chmod 750 "$install_dir" "$data_dir" "$data_dir/uploads" "$data_dir/models"
    chmod 750 "$install_dir/bin/whisper-cli"
    chmod 750 "$install_dir/bin"
}

install_whisper_cpp() {
    local whisper_source="$install_dir/whisper.cpp"
    mkdir -p "$install_dir/bin" "$data_dir/models"
    git clone --depth 1 https://github.com/ggml-org/whisper.cpp.git "$whisper_source"
    cmake -S "$whisper_source" -B "$whisper_source/build" -DBUILD_SHARED_LIBS=OFF -DCMAKE_BUILD_TYPE=Release
    cmake --build "$whisper_source/build" --target whisper-cli --config Release -j "$(nproc)"
    cp "$whisper_source/build/bin/whisper-cli" "$install_dir/bin/whisper-cli"
    curl --fail --location --output "$data_dir/models/ggml-base.bin" https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-base.bin
    ynh_safe_rm "$whisper_source"
}
