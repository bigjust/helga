# -*- mode: ruby -*-
# vi: set ft=ruby :

# Vagrantfile API/syntax version. Don't touch unless you know what you're doing!
VAGRANTFILE_API_VERSION = '2'.freeze

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vm.box = "ubuntu/trusty64"

  # Forward keys from SSH agent rather than copypasta
  config.vm.synced_folder "..", "/vagrant/helga-src"

  # FIXME: Might not even need this much
  config.vm.provider 'virtualbox' do |v|
    v.customize ['modifyvm', :id, '--memory', '1024']
  end

  # Forward ports for irc(6667) and mongo(27017)
  config.vm.network :forwarded_port, guest: 6667, host: 6667
  config.vm.network :forwarded_port, guest: 27017, host: 27017
  config.vm.network :private_network, ip: '192.168.10.101'

  config.vm.provision 'shell', inline: <<EOF
# install newer version of mongodb
sudo apt-key adv --keyserver hkp://keyserver.ubuntu.com:80 --recv 0C49F3730359A14518585931BC711F9BA15703C6
echo "deb [ arch=amd64 ] http://repo.mongodb.org/apt/ubuntu precise/mongodb-org/3.4 multiverse" | sudo tee /etc/apt/sources.list.d/mongodb-org-3.4.list

# Update and install system dependencies
apt-get update -qq
apt-get install -qqy --force-yes \
  git \
  mongodb-org \
  ngircd \
  openssl \
  libssl-dev \
  python-dev \
  python-pip \
  python-setuptools \
  python-virtualenv \
  libffi6 \
  libffi-dev \
  irssi


# Allow external mongo connections
sed -i -s 's/^bind_ip = 127.0.0.1/#bind_ip = 127.0.0.1/' /etc/mongodb.conf
service mongodb restart

# Create a virtualenv for helga and install
sudo -u vagrant virtualenv /home/vagrant/helga_venv
pushd /vagrant
# upgrade pip from the archaic 1.1
sudo -u vagrant /home/vagrant/helga_venv/bin/pip install --upgrade pip
# install helga
sudo -u vagrant /home/vagrant/helga_venv/bin/python setup.py develop
popd

# Make sure the default profile activates the venv
sudo -u vagrant echo "#!/bin/bash" > /home/vagrant/.profile
sudo -u vagrant echo "source /home/vagrant/helga_venv/bin/activate" >> /home/vagrant/.profile
sudo -u vagrant echo "cd /vagrant/" >> /home/vagrant/.profile
EOF

  #config.vm.provision "ansible", run: "never" do |ansible|
  config.vm.provision "ansible" do |ansible|
    #ansible.galaxy_role_file = "ansible/requirements.yml"
    ansible.playbook = "ansible/playbook.yml"
    ansible.groups = {"vagrant" => ['default'],}
  end

end
