# Steps to install and use Transnet-V2

1. **Install requirements**
```
pip install tensorflow[and-cuda] 
```

or use the Tsinghua mirror for faster download in some regions:
```
pip install tensorflow[and-cuda] -i https://pypi.tuna.tsinghua.edu.cn/simple
```

2. **Clone the repository**
```
git clone https://github.com/soCzech/TransNetV2.git
cd TransNetV2
```

3. **Install Transnet-V2 as a Python package**
```
python3 setup.py install
```

4. **Download model weights**

- Run the following command to locate the installed package:
```
pip show transnetv2
```

- You should see output like:
```
Location: /Users/VoThinhPhat/Library/Python/3.9/lib/python/site-packages
```

- Delete the existing `transnetv2-weights/` folder if it exists:
```
rm -rf /Users/VoThinhPhat/Library/Python/3.9/lib/python/site-packages/transnetv2/transnetv2-weights
```

- Download the model weights from:
```
https://github.com/soCzech/TransNetV2/tree/master/inference/transnetv2-weights
```

- Place the downloaded `transnetv2-weights/` folder into:
```
/Users/VoThinhPhat/Library/Python/3.9/lib/python/site-packages/transnetv2/
```

**Note:** The full model weights are not included when installing via pip. You must download them manually.


# Quick Test
```
python3 data_processing/transnetv2_test.py
```