# ha-hitachi-smart-home - 日立智家 Home Assistant 集成

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)

Home Assistant 自定义集成，用于控制**日立 (Hitachi) 中央空调**，通过日立云 API 实现远程控制。

支持标准空调、特殊机型、**智能线控器**以及**新风系统**。

---

## 功能特性

- ✅ UI 配置流程（Config Flow），手机号 + 密码登录
- ✅ 自动发现账户下所有家庭、网关内机及**独立 WiFi 线控器**设备
- ✅ 开/关、温度设置（支持 0.5℃ 步进）、模式切换、风速控制
- ✅ **线控器专属 7 档风速**：自动、微风、超低风、低风、中风、高风、超高风
- ✅ **触控音开关（Switch 实体）**：支持在 HA 中开关线控器按键音
- ✅ **环境传感器（Sensor 实体）**：
  - 室内温度传感器（每台内机/线控器）
  - 室内湿度与 PM2.5 传感器（支持探头的线控器）
  - 家庭室外环境传感器（室外温度、室外湿度、室外 PM2.5、空气质量 AQI）
- ✅ 标准空调/线控器模式：制冷、制热、除湿、送风、自动
- ✅ **新风系统专用支持**（仅风速控制）
- ✅ 每 10 秒自动轮询设备状态，室外天气定时刷新
- ✅ Token 自动刷新（每 24 小时）
- ✅ 完整中英文支持


## 安装方式

### 方式一：HACS（推荐）

1. 确保已安装 [HACS](https://hacs.xyz/)
2. 在 HACS 中添加自定义仓库：`https://github.com/roundRekt/ha-hitachi-smart-home`
3. 类别选择「集成 (Integration)」
4. 搜索 "Hitachi Smart Home" 并安装
5. 重启 Home Assistant

### 方式二：手动安装

```bash
# 进入 custom_components 目录
cd /path/to/your/homeassistant/config/custom_components

# 克隆仓库
git clone https://github.com/roundRekt/ha-hitachi-smart-home.git temp
mv temp/custom_components/hitachi_smart_home .
rm -rf temp
```

或直接下载并解压到 `custom_components/hitachi_smart_home/`。

## 配置

1. 重启 Home Assistant
2. 前往 **设置 → 设备与服务 → 添加集成**
3. 搜索 "Hitachi Smart Home"
4. 输入日立智家的登录信息：
   - **手机号**
   - **密码**
5. 提交后自动完成设备发现

## 支持的设备类型

| 类型 | 说明 | 功能 |
|------|------|------|
| 标准空调 (05) | 普通室内机 | 温度 + 模式 + 风速 |
| 智能线控器 (13/C) | 独立 WiFi 线控器 | 温度 (0.5℃) + 模式 + 风速 |
| 特殊机型 (03) | 特殊室内机 | 温度 + 模式 + 风速 |
| 新风系统 (0D) | 全热交换器/新风 | 仅风速控制 |

## 最低要求

- Home Assistant **2024.1.0** 或更高版本
- 日立智家账号（手机号注册）
- 设备已配网并连接至日立云

## 项目结构

```
custom_components/hitachi_smart_home/
├── __init__.py          # 集成入口
├── api.py               # 云 API 客户端
├── climate.py           # Climate 平台实体（空调控制）
├── switch.py            # Switch 平台实体（按键音开关）
├── sensor.py            # Sensor 平台实体（温湿度/PM2.5/AQI）
├── config_flow.py       # UI 配置流程
├── const.py             # 常量定义
├── coordinator.py       # 数据协调器
├── manifest.json        # 组件清单
├── icon.png             # 图标
├── logo.png             # Logo
├── brand/               # 品牌资源
└── translations/        # 翻译文件
```

## 致谢

本项目通过逆向日立智家Android 应用（版本 7.5.3）的 API 实现，感谢相关社区贡献者。

## 许可证

MIT License - 详见 [LICENSE](LICENSE)
