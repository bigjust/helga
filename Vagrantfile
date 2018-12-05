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
  config.vm.network :forwarded_port, guest: 8080, host: 8080

  #config.vm.provision "ansible", run: "never" do |ansible|
  config.vm.provision "ansible" do |ansible|
    ansible.galaxy_role_file = "ansible/requirements.yml"
    ansible.playbook = "ansible/playbook.yml"
    ansible.groups = {"vagrant" => ['default'],}
  end

end
