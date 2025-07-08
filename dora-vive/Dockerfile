# 使用官方Python基础镜像
FROM python:3.10-slim 

# # 安装系统依赖和uv
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libusb-1.0-0-dev \
    libgtk-3-dev \
    libwebkit2gtk-4.0-dev \
    libssl-dev \
    libsdl2-dev \
    libgstreamer-plugins-base1.0-dev \
    libgstreamer1.0-dev \
    libjpeg-dev \
    libtiff-dev \
    libsm-dev \
    libnotify-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

# 创建工作目录
WORKDIR /app

# 复制项目文件
COPY . .

# 使用uv创建虚拟环境并安装依赖
RUN uv venv
RUN . /app/.venv/bin/activate
RUN uv pip install -e .
RUN /app/.venv/bin/dora build demo.yml --uv

# 设置libsurvive配置文件所需的系统变量，配置文件路径为:XDG_CONFIG_HOME/libsurvive/config.json
ENV XDG_CONFIG_HOME=/app


CMD ["/app/.venv/bin/dora", "run", "demo.yml", "--uv"]
