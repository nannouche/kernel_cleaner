#!/usr/bin/env python3
"""
Désinstallateur automatique du plus ancien noyau Linux non utilisé
Conçu pour les systèmes basés sur DEBIAN
Auteur: Nannouche
"""

import os
import re
import subprocess
import sys
from typing import List, Tuple, Optional
import argparse

class KernelCleaner:
    def __init__(self):
        self.current_kernel = self.get_current_kernel()
        self.verbose = False
        
    def log(self, message: str, level: str = "INFO"):
        """Affiche un message avec un niveau de log"""
        if self.verbose or level == "ERROR":
            print(f"[{level}] {message}")
    
    def get_current_kernel(self) -> str:
        """Récupère la version du noyau actuellement en cours d'utilisation"""
        try:
            result = subprocess.run(['uname', '-r'], capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError:
            raise RuntimeError("Impossible de déterminer le noyau actuel")
    
    def get_installed_kernels(self) -> List[str]:
        """Récupère la liste des noyaux installés"""
        try:
            result = subprocess.run(['dpkg', '-l'], capture_output=True, text=True, check=True)
            kernels = []
            
            for line in result.stdout.split('\n'):
                if 'linux-image-' in line and line.startswith('ii'):
                    parts = line.split()
                    if len(parts) >= 2:
                        package = parts[1]
                        # Extraire la version du noyau du nom du package
                        match = re.search(r'linux-image-(\d+\.\d+\.\d+-\d+)', package)
                        if match:
                            kernel_version = match.group(1)
                            kernels.append(kernel_version)
            
            return sorted(set(kernels))
        except subprocess.CalledProcessError:
            raise RuntimeError("Impossible de lister les noyaux installés")
    
    def parse_kernel_version(self, version: str) -> Tuple[int, int, int, int]:
        """Parse une version de noyau en tuple pour comparaison"""
        match = re.match(r'(\d+)\.(\d+)\.(\d+)-(\d+)', version)
        if match:
            return tuple(map(int, match.groups()))
        raise ValueError(f"Format de version invalide: {version}")
    
    def find_oldest_removable_kernel(self) -> Optional[str]:
        """Trouve le plus ancien noyau qui peut être supprimé"""
        installed_kernels = self.get_installed_kernels()
        
        # Retirer le noyau actuel de la liste
        removable_kernels = [k for k in installed_kernels if k != self.current_kernel]
        
        if not removable_kernels:
            return None
        
        # Garder au moins un noyau de sauvegarde
        if len(removable_kernels) <= 1:
            self.log("Seul le noyau actuel et un noyau de sauvegarde sont installés")
            return None
        
        # Trier par version et prendre le plus ancien
        try:
            removable_kernels.sort(key=self.parse_kernel_version)
            return removable_kernels[0]
        except ValueError as e:
            self.log(f"Erreur lors du tri des versions: {e}", "ERROR")
            return None
    
    def get_kernel_packages(self, kernel_version: str) -> List[str]:
        """Récupère tous les packages associés à une version de noyau"""
        try:
            result = subprocess.run(['dpkg', '-l'], capture_output=True, text=True, check=True)
            packages = []
            
            for line in result.stdout.split('\n'):
                if line.startswith('ii') and kernel_version in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        package = parts[1]
                        # Packages liés au noyau
                        if any(prefix in package for prefix in ['linux-image-', 'linux-headers-', 'linux-modules-']):
                            packages.append(package)
            
            return packages
        except subprocess.CalledProcessError:
            raise RuntimeError("Impossible de lister les packages du noyau")
    
    def remove_kernel(self, kernel_version: str, dry_run: bool = False) -> bool:
        """Supprime un noyau et ses packages associés"""
        packages = self.get_kernel_packages(kernel_version)
        
        if not packages:
            self.log(f"Aucun package trouvé pour le noyau {kernel_version}")
            return False
        
        self.log(f"Packages à supprimer: {', '.join(packages)}")
        
        if dry_run:
            self.log("Mode simulation - aucune suppression effectuée")
            return True
        
        try:
            # Confirmation de sécurité
            if not self.confirm_removal(kernel_version, packages):
                return False
            
            # Suppression des packages
            cmd = ['sudo', 'apt-get', 'remove', '--purge', '-y'] + packages
            self.log(f"Exécution: {' '.join(cmd)}")
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                self.log(f"Noyau {kernel_version} supprimé avec succès")
                
                # Mise à jour de GRUB
                self.log("Mise à jour de GRUB...")
                subprocess.run(['sudo', 'update-grub'], check=True)
                
                return True
            else:
                self.log(f"Erreur lors de la suppression: {result.stderr}", "ERROR")
                return False
                
        except subprocess.CalledProcessError as e:
            self.log(f"Erreur lors de la suppression: {e}", "ERROR")
            return False
    
    def confirm_removal(self, kernel_version: str, packages: List[str]) -> bool:
        """Demande confirmation avant suppression"""
        print(f"\n⚠️  CONFIRMATION REQUISE ⚠️")
        print(f"Noyau actuel: {self.current_kernel}")
        print(f"Noyau à supprimer: {kernel_version}")
        print(f"Packages à supprimer: {len(packages)}")
        
        for pkg in packages:
            print(f"  - {pkg}")
        
        response = input("\nÊtes-vous sûr de vouloir supprimer ce noyau? (oui/non): ").lower().strip()
        return response in ['oui', 'o', 'yes', 'y']
    
    def show_status(self):
        """Affiche le statut des noyaux installés"""
        print(f"Noyau actuel: {self.current_kernel}")
        print(f"Noyaux installés:")
        
        installed_kernels = self.get_installed_kernels()
        for kernel in sorted(installed_kernels, key=self.parse_kernel_version, reverse=True):
            status = " (ACTUEL)" if kernel == self.current_kernel else ""
            print(f"  - {kernel}{status}")
        
        oldest = self.find_oldest_removable_kernel()
        if oldest:
            print(f"\nPlus ancien noyau supprimable: {oldest}")
        else:
            print(f"\nAucun noyau supprimable trouvé")
    
    def run(self, dry_run: bool = False, show_status: bool = False):
        """Fonction principale"""
        self.log(f"Démarrage du nettoyage des noyaux Linux")
        self.log(f"Noyau actuel: {self.current_kernel}")
        
        if show_status:
            self.show_status()
            return
        
        oldest_kernel = self.find_oldest_removable_kernel()
        
        if not oldest_kernel:
            print("Aucun noyau ancien à supprimer.")
            return
        
        print(f"Plus ancien noyau trouvé: {oldest_kernel}")
        
        if self.remove_kernel(oldest_kernel, dry_run):
            if not dry_run:
                print("✅ Noyau supprimé avec succès!")
                print("🔄 Redémarrage recommandé pour finaliser les changements.")
        else:
            print("❌ Échec de la suppression du noyau.")

def main():
    parser = argparse.ArgumentParser(description="Désinstalle le plus ancien noyau Linux non utilisé")
    parser.add_argument('-v', '--verbose', action='store_true', help='Mode verbeux')
    parser.add_argument('-n', '--dry-run', action='store_true', help='Simulation sans suppression')
    parser.add_argument('-s', '--status', action='store_true', help='Affiche le statut des noyaux')
    
    args = parser.parse_args()
    
    # Vérification des privilèges root (sauf pour --status et --dry-run)
    if not args.dry_run and not args.status and os.geteuid() != 0:
        print("⚠️  Ce script nécessite les privilèges root pour supprimer les noyaux.")
        print("Exécutez avec: sudo python3 kernel_cleaner.py")
        sys.exit(1)
    
    try:
        cleaner = KernelCleaner()
        cleaner.verbose = args.verbose
        cleaner.run(dry_run=args.dry_run, show_status=args.status)
        
    except KeyboardInterrupt:
        print("\n\nInterruption par l'utilisateur.")
        sys.exit(1)
    except Exception as e:
        print(f"Erreur: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()