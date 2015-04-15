import hudson.model.*

listAllJobs(Hudson.instance.items)

def listAllJobs(items) {
  for (item in items) {
    if (item.class.canonicalName != 'com.cloudbees.hudson.plugins.folder.Folder') {
        if (item.class.canonicalName) {
            print('[' + item.class.canonicalName + ']: ')
            println(item.name)
        }
    } else {
        //print('[' + item.class.canonicalName + ']: ')
        //println(item.name)
        listAllJobs(((com.cloudbees.hudson.plugins.folder.Folder) item).getItems())
    }
  }
}
